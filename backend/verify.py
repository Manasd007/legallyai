"""Citation verification + weak-retrieval hedge (brief §6.5) — MANDATORY guard.

Every cited case must trace to a document in the retrieved set. Anything else
is stripped. If verification empties the citations, or max retrieval similarity
was below threshold, we override the outcome to Uncertain and hedge honestly.
This is the single most important anti-hallucination step.
"""
from __future__ import annotations

import logging
import re

from config import get_settings
from retrieval import RetrievalResult

log = logging.getLogger("legally.verify")

WEAK_RETRIEVAL_MESSAGE = (
    "I couldn't find closely matching precedents for this situation in the "
    "corpus, so I can't offer a confident, well-grounded prediction. Treat the "
    "notes below as tentative and consult a qualified advocate."
)


def _norm(s: str) -> str:
    """Loose normalization so 'AIR 2019 SC 123' == 'air 2019 sc 123.'."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _best_chunk_for(cite: dict, result: RetrievalResult):
    """Find the retrieved chunk that grounds a citation (best similarity match)."""
    key_c = _norm(cite.get("citation", ""))
    key_n = _norm(cite.get("case_name", ""))
    best = None
    for c in result.chunks:
        if (key_c and _norm(c.citation) == key_c) or (key_n and _norm(c.case_name) == key_n):
            if best is None or c.similarity_score > best.similarity_score:
                best = c
    return best


def verify(prediction: dict, result: RetrievalResult) -> dict:
    """Return a verified copy of the prediction with a `verification` block.

    Each KEPT citation is enriched with `source`: the exact passage from the real
    judgment that grounds it, so the UI can let users trace every claim (provenance).
    """
    s = get_settings()
    retrieved_citations = {_norm(c.citation) for c in result.chunks if c.citation}
    retrieved_names = {_norm(c.case_name) for c in result.chunks if c.case_name}

    kept, stripped = [], []
    for cite in prediction.get("cited_cases", []):
        key_c = _norm(cite.get("citation", ""))
        key_n = _norm(cite.get("case_name", ""))
        if (key_c and key_c in retrieved_citations) or (key_n and key_n in retrieved_names):
            chunk = _best_chunk_for(cite, result)
            enriched = dict(cite)
            if chunk is not None:
                from textutil import clean_excerpt

                excerpt = clean_excerpt(chunk.chunk_text)
                enriched["source"] = {
                    "court": chunk.court,
                    "year": chunk.year,
                    "outcome": chunk.outcome,
                    "segment_role": chunk.segment_role,
                    "excerpt": excerpt[:900] + ("…" if len(excerpt) > 900 else ""),
                    "similarity": round(chunk.similarity_score, 3),
                    "chunk_id": chunk.chunk_id,
                }
            kept.append(enriched)
        else:
            stripped.append(cite)
            log.warning("Stripped unverified citation: %s", cite)

    out = dict(prediction)
    out["cited_cases"] = kept

    weak = result.max_similarity < s.similarity_threshold
    hedged = False
    if weak or not kept:
        out["likely_outcome"] = "Uncertain"
        out["confidence"] = "low"
        if not out.get("reasoning") or weak or not kept:
            out["reasoning"] = WEAK_RETRIEVAL_MESSAGE + (
                ("\n\n" + out["reasoning"]) if out.get("reasoning") else ""
            )
        hedged = True

    out["verification"] = {
        "max_similarity": round(result.max_similarity, 4),
        "threshold": s.similarity_threshold,
        "weak_retrieval": weak,
        "stripped_citations": stripped,
        "verified_count": len(kept),
        "fabricated_count": len(stripped),
        "hedged": hedged,
        "retrieved_ids": [c.chunk_id for c in result.chunks],
    }
    return out
