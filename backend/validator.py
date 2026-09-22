from __future__ import annotations

import json
import logging
import re
from typing import Literal, TypedDict

from config import get_settings, load_prompt
from ensemble import llm_outcome_to_label, outcome_to_label
from llm import complete
from retrieval import RetrievalResult

log = logging.getLogger("legally.validator")

Verdict = Literal["pass", "revise"]
_VALID_CONF = {"low", "medium", "high"}
_CONF_RANK = {"low": 0, "medium": 1, "high": 2}

_DECISIVE_ROLES = {"ratio", "holding", "issues"}

_WIN_WORDS = ("allow", "set aside", "set-aside", "grant", "quash", "reinstat", "in favour of the appell", "in favour of the petition")
_LOSE_WORDS = ("dismiss", "reject", "upheld the dismissal", "against the appell", "against the petition", "denied relief")


class Critique(TypedDict):
    verdict: Verdict
    issues: list[str]
    unsupported_claims: list[str]
    max_confidence: str | None
    feedback: str
    checks: dict
    ok: bool


def _pass(ok: bool = True) -> Critique:
    return {
        "verdict": "pass",
        "issues": [],
        "unsupported_claims": [],
        "max_confidence": None,
        "feedback": "",
        "checks": {},
        "ok": ok,
    }


def _claimed_direction(text: str) -> int | None:
    t = (text or "").lower()
    win = any(w in t for w in _WIN_WORDS)
    lose = any(w in t for w in _LOSE_WORDS)
    if win and not lose:
        return 1
    if lose and not win:
        return 0
    return None


def _match_chunk(cite: dict, result: RetrievalResult):
    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    kc, kn = norm(cite.get("citation", "")), norm(cite.get("case_name", ""))
    for c in result.chunks:
        if (kc and norm(c.citation) == kc) or (kn and norm(c.case_name) == kn):
            return c
    return None


def check_citation_outcomes(cited_cases: list[dict], result: RetrievalResult) -> dict:
    mismatches = []
    for cite in cited_cases or []:
        chunk = _match_chunk(cite, result)
        if chunk is None:
            continue
        real = outcome_to_label(chunk.outcome)
        claimed = _claimed_direction(cite.get("relevance", "") or cite.get("excerpt", ""))
        if real is not None and claimed is not None and real != claimed:
            mismatches.append({
                "case_name": chunk.case_name,
                "citation": chunk.citation,
                "recorded_outcome": chunk.outcome,
                "described_as": "won/allowed" if claimed == 1 else "lost/dismissed",
            })
    return {"ok": not mismatches, "mismatches": mismatches}


def check_evidence_quality(result: RetrievalResult) -> dict:
    roles = [(c.segment_role or "").strip().lower() for c in result.chunks]
    decisive = [r for r in roles if r in _DECISIVE_ROLES]
    return {
        "ok": bool(decisive),
        "decisive_segments": len(decisive),
        "retrieved_segments": len(roles),
        "roles": roles,
    }


def check_ensemble_coherence(
    llm_outcome: str, precedent: dict | None, classifier: dict | None
) -> dict:
    llm = llm_outcome_to_label(llm_outcome)
    if llm is None:
        return {"applicable": False, "agree": None, "conflicts": []}

    conflicts = []
    signals = 0
    if precedent and precedent.get("applicable") and precedent.get("win_probability") is not None:
        signals += 1
        prec_label = 1 if float(precedent["win_probability"]) >= 0.5 else 0
        if prec_label != llm:
            conflicts.append(
                f"the real outcomes of the {precedent.get('n_cases', 0)} closest "
                f"precedents lean {'applicant-wins' if prec_label else 'applicant-loses'}, "
                f"opposite the model's {llm_outcome}"
            )
    if classifier and classifier.get("available") and classifier.get("win_probability") is not None:
        signals += 1
        clf_label = 1 if float(classifier["win_probability"]) >= 0.5 else 0
        if clf_label != llm:
            conflicts.append(
                f"the trained classifier leans {'applicant-wins' if clf_label else 'applicant-loses'}, "
                f"opposite the model's {llm_outcome}"
            )
    return {
        "applicable": signals > 0,
        "agree": (signals > 0 and not conflicts),
        "signals_compared": signals,
        "conflicts": conflicts,
    }


def _cap_confidence(current: str | None, ceiling: str) -> str:
    cur = current if current in _VALID_CONF else "low"
    if _CONF_RANK.get(cur, 0) <= _CONF_RANK[ceiling]:
        return cur
    return ceiling


def _clean(text: str) -> str:
    from textutil import normalize_text

    return normalize_text(text)


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t[3:]
        t = t.removeprefix("json").strip().removesuffix("```").strip()
    return t


def _findings_block(det: dict) -> str:
    lines = []
    co = det.get("citation_outcomes", {})
    if co.get("mismatches"):
        for m in co["mismatches"]:
            lines.append(
                f"- OUTCOME MISMATCH: the draft describes {m['case_name']} as "
                f"{m['described_as']}, but the corpus records it as "
                f"'{m['recorded_outcome']}'. Verify and fix."
            )
    eq = det.get("evidence_quality", {})
    if eq and not eq.get("ok", True):
        lines.append(
            "- WEAK EVIDENCE: no Ratio/Holding segment was retrieved, only "
            f"{eq.get('roles')}. Any firm legal proposition is under-grounded."
        )
    ec = det.get("ensemble_coherence", {})
    if ec.get("conflicts"):
        for c in ec["conflicts"]:
            lines.append(f"- SIGNAL CONFLICT: {c}. The verdict must be hedged accordingly.")
    return "\n".join(lines) if lines else "(no automated red flags)"


def _llm_critique(question: str, context_block: str, draft: str, det: dict) -> Critique:
    if not get_settings().validation_enabled or not (draft or "").strip():
        return _pass()
    user = (
        f"QUESTION:\n{question}\n\n"
        f"RETRIEVED CASES (the only permissible basis):\n{context_block}\n\n"
        f"AUTOMATED LEGAL CHECKS (already run against the corpus metadata):\n"
        f"{_findings_block(det)}\n\n"
        f"DRAFT ANSWER:\n{draft}\n\n"
        "Review the DRAFT now and return the JSON verdict."
    )
    try:
        raw = complete(
            model=get_settings().validator_model,
            system=load_prompt("validator_v1.txt"),
            user=user,
            temperature=0.0,
            json_mode=True,
            max_tokens=1200,
            reasoning_effort="low",
            seed=get_settings().llm_seed,
        )
        data = json.loads(_strip_fences(raw))
        verdict = data.get("verdict")
        if verdict not in ("pass", "revise"):
            verdict = "pass"
        conf = data.get("max_confidence")
        if conf not in _VALID_CONF:
            conf = None
        return {
            "verdict": verdict,  # type: ignore[typeddict-item]
            "issues": [_clean(str(x).strip()) for x in (data.get("issues") or []) if str(x).strip()],
            "unsupported_claims": [
                _clean(str(x).strip()) for x in (data.get("unsupported_claims") or []) if str(x).strip()
            ],
            "max_confidence": conf,
            "feedback": _clean(str(data.get("feedback", "")).strip()),
            "checks": {},
            "ok": True,
        }
    except json.JSONDecodeError as e:
        log.warning("Validator invalid JSON; passing draft: %s", e)
        return _pass(ok=False)
    except Exception as e:  # noqa: BLE001 - a flaky critic must never block the answer
        log.warning("Validator call failed; passing draft: %s", e)
        return _pass(ok=False)


def review(
    *,
    question: str,
    context_block: str,
    draft: str,
    result: RetrievalResult,
    cited_cases: list[dict] | None = None,
    llm_outcome: str | None = None,
    precedent: dict | None = None,
    classifier: dict | None = None,
) -> Critique:
    det = {
        "citation_outcomes": check_citation_outcomes(cited_cases or [], result),
        "evidence_quality": check_evidence_quality(result),
    }
    if llm_outcome is not None:
        det["ensemble_coherence"] = check_ensemble_coherence(llm_outcome, precedent, classifier)

    hard_issues: list[str] = []
    ceiling: str | None = None
    co = det["citation_outcomes"]
    if not co["ok"]:
        for m in co["mismatches"]:
            hard_issues.append(
                f"{m['case_name']} is described as {m['described_as']} but was recorded "
                f"as '{m['recorded_outcome']}'."
            )
    ec = det.get("ensemble_coherence", {})
    if ec.get("conflicts"):
        hard_issues.extend(ec["conflicts"])
        ceiling = "low"
    if not det["evidence_quality"]["ok"]:
        ceiling = _cap_confidence(ceiling or "medium", "medium")

    crit = _llm_critique(question, context_block, draft, det)
    crit["checks"] = det

    if hard_issues:
        crit["issues"] = hard_issues + crit["issues"]
        crit["verdict"] = "revise"
        det_feedback = " ".join(hard_issues)
        crit["feedback"] = (det_feedback + " " + crit["feedback"]).strip()
    else:
        crit["verdict"] = "pass"

    crit["max_confidence"] = ceiling
    return crit


def critique(*, question: str, context_block: str, draft: str) -> Critique:
    return review(
        question=question,
        context_block=context_block,
        draft=draft,
        result=RetrievalResult(),
    )


def public_view(c: Critique) -> dict:
    checks = c.get("checks") or {}
    return {
        "validated": True,
        "verdict": c["verdict"],
        "revised": False,
        "issue_count": len(c["issues"]),
        "issues": c["issues"][:5],
        "confidence_ceiling": c.get("max_confidence"),
        "checks": {
            "citation_outcomes_ok": (checks.get("citation_outcomes") or {}).get("ok", True),
            "has_decisive_precedent": (checks.get("evidence_quality") or {}).get("ok", True),
            "signals_agree": (checks.get("ensemble_coherence") or {}).get("agree"),
        },
        "critic_ran": c["ok"],
    }
