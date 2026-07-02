"""Win/lose (1/0) prediction ensemble — the novel part (brief §2, §10).

We never ship a bare LLM guess for "did the applicant win". Instead we combine
up to THREE independent signals and judge our own confidence by how much they
AGREE:

  1. precedent_vote  — count the REAL outcomes of the retrieved analogous cases
                       (uses `outcome`/disposal_nature we store at ingest). This
                       is grounded in decided cases, not the model's imagination.
  2. llm_forecast    — the reasoning model's Granted/Dismissed call.
  3. classifier      — an offline PredEx-trained InLegalBERT probability
                       (optional; absent until trained — see pipeline/finetune).

Honesty rules (brief §2):
  * 1 = applicant (appellant/petitioner) prevailed; 0 = did not.
  * Only meaningful for appeal-shaped questions. If the LLM returned "Uncertain"
    (e.g. a non-appellate tenancy/consumer situation) we still surface the
    precedent lean but mark it advisory, never a verdict.
  * Always a probability with the underlying cases attached.
"""
from __future__ import annotations

from config import get_settings
from retrieval import RetrievalResult


def outcome_to_label(outcome: str) -> int | None:
    """Map a recorded disposal/outcome string to 1 (win) / 0 (loss) / None."""
    o = (outcome or "").lower()
    if "partly" in o or "part allowed" in o:
        return None  # genuinely mixed — don't force a side
    if "allow" in o or "granted" in o or "set aside" in o:
        return 1
    if "dismiss" in o or "rejected" in o:
        return 0
    return None  # "disposed of", "withdrawn", unknown -> no clear side


def llm_outcome_to_label(likely_outcome: str) -> int | None:
    return {"Granted": 1, "Dismissed": 0}.get(likely_outcome)


def precedent_vote(result: RetrievalResult) -> dict:
    """Similarity-weighted win-probability from the retrieved precedents' real outcomes."""
    s = get_settings()
    # Collapse to one (best) chunk per case so a case isn't counted many times.
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
        return "low"  # signals disagree -> be humble
    if n_signals >= 3:
        return "high"
    if n_signals == 2:
        return "medium"
    return "low"  # a single lone signal


def combine(
    *,
    precedent: dict,
    llm_outcome: str,
    classifier: dict | None,
) -> dict:
    """Blend available signals into a final 1/0 + an agreement-aware confidence."""
    probs: list[float] = []
    labels: list[int] = []
    used: list[str] = []

    if precedent.get("applicable") and precedent.get("win_probability") is not None:
        p = float(precedent["win_probability"])
        probs.append(p)
        labels.append(1 if p >= 0.5 else 0)
        used.append("precedent_vote")

    llm_label = llm_outcome_to_label(llm_outcome)
    if llm_label is not None:
        probs.append(float(llm_label))
        labels.append(llm_label)
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
