from __future__ import annotations

import logging

import chat_intake as chat_intake_mod
import context_assembly
from config import get_settings, load_prompt
from llm import complete
import reformulate as reformulate_mod
import retrieval as retrieval_mod
import validator as validator_mod

log = logging.getLogger("legally.qa")


def _convo(history: list[dict], limit: int = 6) -> str:
    turns = history[-limit:]
    return "\n".join(
        f"{h.get('role', 'user').upper()}: {h.get('content', '')}" for h in turns
    ) or "(none)"


def _retrieval_query(question: str, history: list[dict]) -> str:
    prior = [h["content"] for h in history if h.get("role") == "user"][-2:]
    return " ".join([*prior, question]).strip() if prior else question


def _dedupe_cases(result: retrieval_mod.RetrievalResult, limit: int = 5) -> list[dict]:
    by_case: dict[str, dict] = {}
    for c in result.chunks:
        key = (c.citation or c.case_name).strip()
        if not key:
            continue
        if key not in by_case or c.similarity_score > by_case[key]["similarity"]:
            from textutil import clean_excerpt

            excerpt = clean_excerpt(c.chunk_text)
            by_case[key] = {
                "case_name": c.case_name,
                "citation": c.citation,
                "court": c.court,
                "year": c.year,
                "outcome": c.outcome,
                "similarity": round(c.similarity_score, 3),
                "segment_role": c.segment_role,
                "excerpt": excerpt[:900] + ("…" if len(excerpt) > 900 else ""),
                "chunk_id": c.chunk_id,
            }
    cases = sorted(by_case.values(), key=lambda d: d["similarity"], reverse=True)
    return cases[:limit]


def _format_context(result: retrieval_mod.RetrievalResult) -> str:
    try:
        return context_assembly.format_context(result)
    except Exception as e:  # noqa: BLE001 - never fail the answer on formatting
        log.warning("Case assembly failed (%s); using flat chunk context.", e)
    parts = []
    for i, c in enumerate(result.chunks, 1):
        parts.append(
            f"[{i}] {c.case_name} | {c.citation} | {c.court} {c.year or ''}\n"
            f"    recorded_outcome: {c.outcome}\n"
            f"    segment ({c.segment_role}): {c.chunk_text}"
        )
    return "\n\n".join(parts) if parts else "(no relevant cases were retrieved)"


def _empty(answer: str, mode: str) -> dict:
    return {
        "answer": answer,
        "cited_cases": [],
        "weak_retrieval": False,
        "max_similarity": 0.0,
        "mode": mode,
    }


def _smalltalk(question: str, history: list[dict]) -> dict:
    s = get_settings()
    user = f"CONVERSATION SO FAR:\n{_convo(history)}\n\nLATEST MESSAGE: {question}"
    try:
        text = complete(
            model=s.reasoning_model,
            system=load_prompt("chat_smalltalk_v1.txt"),
            user=user,
            temperature=0.4,
            max_tokens=600,
            reasoning_effort="low",
        ).strip()
    except Exception as e:  # noqa: BLE001
        log.error("smalltalk reply failed: %s", e)
        text = (
            "Hi! Tell me what happened in your legal matter, ask a legal question, "
            "or attach a document and I'll take a look."
        )
    return _empty(text, "smalltalk")


def _general(question: str, history: list[dict]) -> dict:
    s = get_settings()
    user = f"CONVERSATION SO FAR:\n{_convo(history)}\n\nQUESTION: {question}"
    try:
        text = complete(
            model=s.reasoning_model,
            system=load_prompt("general_legal_v2.txt"),
            user=user,
            temperature=0.3,
            max_tokens=1000,
            reasoning_effort="low",
        ).strip()
    except Exception as e:  # noqa: BLE001
        log.error("general reply failed: %s", e)
        text = "I'm unable to answer that right now. Please try again shortly."
    return _empty(text, "general")


def answer(question: str, history: list[dict]) -> dict:
    mode = chat_intake_mod.classify(question, history)
    if mode == "smalltalk":
        result = _smalltalk(question, history)
    elif mode == "general":
        result = _general(question, history)
    else:
        result = _grounded(question, history)
    from textutil import normalize_text

    if isinstance(result.get("answer"), str):
        result["answer"] = normalize_text(result["answer"])
    return result


def _grounded(question: str, history: list[dict]) -> dict:
    s = get_settings()

    rq = _retrieval_query(question, history)
    reformulated = reformulate_mod.reformulate(rq)
    result = retrieval_mod.retrieve(reformulated, rq)

    cases = _dedupe_cases(result)
    weak = result.max_similarity < s.similarity_threshold

    convo = ""
    for h in history[-6:]:
        convo += f"{h.get('role', 'user').upper()}: {h.get('content', '')}\n"

    system = load_prompt("legal_qa_system_v1.txt")
    context_block = _format_context(result)
    base_user = (
        f"CONVERSATION SO FAR:\n{convo or '(none)'}\n\n"
        "RETRIEVED CASES (the ONLY permissible basis for legal statements):\n"
        f"{context_block}\n\n"
        f"USER QUESTION: {question}\n\n"
        + (
            "Note: retrieval was weak for this question — be upfront that you "
            "couldn't find strongly on-point cases, and answer cautiously.\n"
            if weak
            else ""
        )
        + "Answer grounded only in the retrieved cases."
    )

    _ERR = "I'm unable to answer that right now. Please try again shortly."

    def _draft(user: str) -> str | None:
        try:
            return complete(
                model=s.reasoning_model,
                system=system,
                user=user,
                temperature=0.25,
                max_tokens=1600,
                reasoning_effort="low",
            ).strip()
        except Exception as e:  # noqa: BLE001
            log.error("Legal QA failed: %s", e)
            return None

    text = _draft(base_user)
    validation = validator_mod.public_view(validator_mod._pass(ok=False))

    if text is None:
        text = _ERR
    else:
        crit = validator_mod.review(
            question=question,
            context_block=context_block,
            draft=text,
            result=result,
        )
        validation = validator_mod.public_view(crit)
        if crit["verdict"] == "revise" and crit["ok"]:
            revise_user = (
                base_user
                + "\n\nA REVIEWER FLAGGED YOUR PREVIOUS DRAFT. Fix these issues: "
                + crit["feedback"]
                + "\nGround every legal statement strictly in the cases above. Remove "
                "or plainly qualify anything they do not squarely support, and do not "
                "overstate a case beyond what it decided. If the cases do not actually "
                "answer the question, say so. Rewrite the full answer."
            )
            revised = _draft(revise_user)
            if revised:
                text = revised
                validation["revised"] = True
                crit = validator_mod.review(
                    question=question,
                    context_block=context_block,
                    draft=text,
                    result=result,
                )
                validation = validator_mod.public_view(crit)
                validation["revised"] = True

    caution = validation.get("verdict") == "revise" or not validation.get(
        "checks", {}
    ).get("citation_outcomes_ok", True)

    return {
        "answer": text,
        "cited_cases": cases,
        "weak_retrieval": weak,
        "grounding_caution": caution,
        "max_similarity": round(result.max_similarity, 4),
        "mode": "case_law",
        "validation": validation,
    }
