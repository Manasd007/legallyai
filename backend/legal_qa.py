"""Conversational legal Q&A grounded in the case-law corpus (the "Legal Q&A
Assistant" feature).

Distinct from doc_analyze.chat (which is grounded in ONE uploaded document): this
answers free-form legal questions grounded in cases retrieved from the FAISS corpus,
and keeps conversational context so follow-up questions work.
"""
from __future__ import annotations

import logging

import chat_intake as chat_intake_mod
from config import get_settings, load_prompt
from llm import complete
import reformulate as reformulate_mod
import retrieval as retrieval_mod

log = logging.getLogger("legally.qa")


def _convo(history: list[dict], limit: int = 6) -> str:
    turns = history[-limit:]
    return "\n".join(
        f"{h.get('role', 'user').upper()}: {h.get('content', '')}" for h in turns
    ) or "(none)"


def _retrieval_query(question: str, history: list[dict]) -> str:
    """Build a standalone retrieval query so follow-ups carry prior context.

    Cheap: prepend the last couple of user turns to the current question rather
    than spending an extra LLM call to rewrite it."""
    prior = [h["content"] for h in history if h.get("role") == "user"][-2:]
    return " ".join([*prior, question]).strip() if prior else question


def _dedupe_cases(result: retrieval_mod.RetrievalResult, limit: int = 5) -> list[dict]:
    """Collapse chunks to one entry per case (best similarity), for display."""
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
    parts = []
    for i, c in enumerate(result.chunks, 1):
        parts.append(
            f"[{i}] {c.case_name} | {c.citation} | {c.court} {c.year or ''}\n"
            f"    recorded_outcome: {c.outcome}\n"
            f"    segment ({c.segment_role}): {c.chunk_text}"
        )
    return "\n\n".join(parts) if parts else "(no relevant cases were retrieved)"


def _empty(answer: str, mode: str) -> dict:
    """Shape for a non-grounded reply (no retrieval, no citations)."""
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
            max_tokens=160,
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
            max_tokens=420,
        ).strip()
    except Exception as e:  # noqa: BLE001
        log.error("general reply failed: %s", e)
        text = "I'm unable to answer that right now. Please try again shortly."
    return _empty(text, "general")


def answer(question: str, history: list[dict]) -> dict:
    # Decide how to handle this turn before touching the corpus, so greetings,
    # meta questions and off-topic chatter don't trigger case retrieval.
    mode = chat_intake_mod.classify(question, history)
    if mode == "smalltalk":
        return _smalltalk(question, history)
    if mode == "general":
        return _general(question, history)
    return _grounded(question, history)


def _grounded(question: str, history: list[dict]) -> dict:
    s = get_settings()

    rq = _retrieval_query(question, history)
    reformulated = reformulate_mod.reformulate(rq)
    result = retrieval_mod.retrieve(reformulated, rq)  # may raise FileNotFoundError

    cases = _dedupe_cases(result)
    weak = result.max_similarity < s.similarity_threshold

    convo = ""
    for h in history[-6:]:
        convo += f"{h.get('role', 'user').upper()}: {h.get('content', '')}\n"

    system = load_prompt("legal_qa_system_v1.txt")
    user = (
        f"CONVERSATION SO FAR:\n{convo or '(none)'}\n\n"
        "RETRIEVED CASES (the ONLY permissible basis for legal statements):\n"
        f"{_format_context(result)}\n\n"
        f"USER QUESTION: {question}\n\n"
        + (
            "Note: retrieval was weak for this question — be upfront that you "
            "couldn't find strongly on-point cases, and answer cautiously.\n"
            if weak
            else ""
        )
        + "Answer grounded only in the retrieved cases."
    )

    try:
        text = complete(
            model=s.reasoning_model,
            system=system,
            user=user,
            temperature=0.25,
            max_tokens=800,
        ).strip()
    except Exception as e:  # noqa: BLE001
        log.error("Legal QA failed: %s", e)
        text = "I'm unable to answer that right now. Please try again shortly."

    return {
        "answer": text,
        "cited_cases": cases,
        "weak_retrieval": weak,
        "max_similarity": round(result.max_similarity, 4),
        "mode": "case_law",
    }
