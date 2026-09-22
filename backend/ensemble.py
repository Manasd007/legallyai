from __future__ import annotations

from config import get_settings
from retrieval import RetrievalResult


def outcome_to_label(outcome: str) -> int | None:
    o = (outcome or "").lower()
    if "partly" in o or "part allowed" in o:
        return None
    if "allow" in o or "granted" in o or "set aside" in o:
        return 1
    if "dismiss" in o or "rejected" in o:
        return 0
    return None


def llm_outcome_to_label(likely_outcome: str) -> int | None:
    return {"Granted": 1, "Dismissed": 0}.get(likely_outcome)


def precedent_vote(result: RetrievalResult) -> dict:
    s = get_settings()
    by_case: dict[str, object] = {}
    for c in result.chunks:
        key = (c.citation or c.case_name).strip()
        if not key:
            continue
        if key not in by_case or c.similarity_score > by_case[key].similarity_score:
            by_case[key] = c

    decided = []
    for c in by_case.values():
        label = outcome_to_label(c.outcome)
        if label is not None:
            decided.append((c, label))

    n = len(decided)
    if n == 0:
        return {
            "applicable": False,
            "win_probability": None,
            "n_cases": 0,
            "won": 0,
            "lost": 0,
            "cases": [],
        }

    wsum = sum(c.similarity_score for c, _ in decided) or float(n)
    win_p = sum(c.similarity_score * lbl for c, lbl in decided) / wsum
    won = sum(1 for _, l in decided if l == 1)
    return {
        "applicable": n >= s.min_precedents_for_vote,
        "win_probability": round(win_p, 3),
        "n_cases": n,
        "won": won,
        "lost": n - won,
        "cases": [
            {
                "case_name": c.case_name,
                "citation": c.citation,
                "outcome": c.outcome,
                "label": lbl,
                "similarity": round(c.similarity_score, 3),
            }
            for c, lbl in decided
        ],
    }


def _confidence(n_signals: int, agree: bool, final_prob: float | None, precedent: dict) -> str:
    if n_signals == 0 or not agree:
        return "low"
    decisive = final_prob is not None and abs(final_prob - 0.5) >= 0.15
    strong_precedent = bool(precedent.get("applicable")) and precedent.get("n_cases", 0) >= 3
    if n_signals >= 3 and decisive and strong_precedent:
        return "high"
    if n_signals >= 2:
        return "medium"
    return "low"


def combine(
    *,
    precedent: dict,
    llm_outcome: str,
    classifier: dict | None,
    llm_confidence: str | None = None,
) -> dict:
    grounded: list[tuple[float, float]] = []
    labels: list[int] = []
    used: list[str] = []

    if precedent.get("applicable") and precedent.get("win_probability") is not None:
        p = float(precedent["win_probability"])
        grounded.append((p, float(min(precedent.get("n_cases", 0), 5) or 1)))
        labels.append(1 if p >= 0.5 else 0)
        used.append("precedent_vote")

    llm_label = llm_outcome_to_label(llm_outcome)
    if llm_label is not None:
        labels.append(llm_label)
        used.append("llm_forecast")

    if classifier and classifier.get("available") and classifier.get("win_probability") is not None:
        cp = float(classifier["win_probability"])
        grounded.append((cp, 2.0))
        labels.append(1 if cp >= 0.5 else 0)
        used.append("classifier")

    n = len(labels)
    if not grounded:
        return {
            "final_win_probability": None,
            "final_label": None,
            "agreement": "insufficient" if n else "none",
            "confidence": "low",
            "signals_used": used,
            "note": (
                "No decided analogous precedent or classifier signal was available, "
                "so no percentage is shown; the notes below rest on the written "
                "analysis alone and should be treated as tentative."
            ),
        }

    wsum = sum(w for _, w in grounded)
    final_prob = round(sum(pr * w for pr, w in grounded) / wsum, 3)
    final_label = 1 if final_prob >= 0.5 else 0

    agree = len(set(labels)) == 1
    agreement = "single" if n == 1 else ("high" if agree else "mixed")

    note = None
    if llm_label is None:
        note = (
            "The written analysis did not commit to a win/lose verdict; the figure "
            "reflects how analogous past cases were decided, not a predicted verdict."
        )
    elif not agree:
        note = (
            "The independent signals do not fully agree, so confidence is held low "
            "and the estimate should be read with caution."
        )

    return {
        "final_win_probability": final_prob,
        "final_label": final_label,
        "agreement": agreement,
        "confidence": _confidence(n, agree, final_prob, precedent),
        "signals_used": used,
        "note": note,
    }
