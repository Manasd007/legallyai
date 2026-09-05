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


_LLM_PROB = {
    ("Granted", "high"): 0.85, ("Granted", "medium"): 0.72, ("Granted", "low"): 0.60,
    ("Dismissed", "high"): 0.15, ("Dismissed", "medium"): 0.28, ("Dismissed", "low"): 0.40,
}


def llm_outcome_to_prob(likely_outcome: str, confidence: str | None) -> float | None:
    if likely_outcome not in ("Granted", "Dismissed"):
        return None
    return _LLM_PROB.get((likely_outcome, confidence or "low"), 0.5)


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


def _confidence(n_signals: int, agree: bool) -> str:
    if n_signals == 0:
        return "low"
    if not agree:
        return "low"
    if n_signals >= 3:
        return "high"
    if n_signals == 2:
        return "medium"
    return "low"


def combine(
    *,
    precedent: dict,
    llm_outcome: str,
    classifier: dict | None,
    llm_confidence: str | None = None,
) -> dict:
    probs: list[float] = []
    labels: list[int] = []
    used: list[str] = []

    if precedent.get("applicable") and precedent.get("win_probability") is not None:
        p = float(precedent["win_probability"])
        probs.append(p)
        labels.append(1 if p >= 0.5 else 0)
        used.append("precedent_vote")

    llm_label = llm_outcome_to_label(llm_outcome)
    llm_prob = llm_outcome_to_prob(llm_outcome, llm_confidence)
    if llm_prob is not None:
        probs.append(llm_prob)
        labels.append(1 if llm_prob >= 0.5 else 0)
        used.append("llm_forecast")

    if classifier and classifier.get("available") and classifier.get("win_probability") is not None:
        cp = float(classifier["win_probability"])
        probs.append(cp)
        labels.append(1 if cp >= 0.5 else 0)
        used.append("classifier")

    n = len(labels)
    if n == 0:
        return {
            "final_win_probability": None,
            "final_label": None,
            "agreement": "none",
            "confidence": "low",
            "signals_used": [],
            "note": "No appeal-shaped signal available; treat as a non-verdict situation.",
        }

    agree = all(l == labels[0] for l in labels)
    final_prob = round(sum(probs) / n, 3)
    final_label = 1 if final_prob >= 0.5 else 0
    agreement = "single" if n == 1 else ("high" if agree else "mixed")

    note = None
    if llm_label is None and used:
        note = (
            "The reasoning model did not give a binary verdict (likely a "
            "non-appellate situation); the figure below reflects how analogous "
            "past cases were decided, not a predicted verdict."
        )

    return {
        "final_win_probability": final_prob,
        "final_label": final_label,
        "agreement": agreement,
        "confidence": _confidence(n, agree),
        "signals_used": used,
        "note": note,
    }
