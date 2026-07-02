"""Hybrid top-k retrieval over the FAISS corpus index (brief §6.3).

v1 vector backend is local FAISS (chosen for cost at scale). The index and a
parallel metadata table (parquet) are built offline by pipeline/chunk_embed.py.

Hybrid search = semantic (FAISS cosine) + keyword (lightweight BM25-ish term
overlap over the candidate pool). Pure keyword/BM25 over the full corpus would
need a separate index; for v1 we re-rank the vector candidates by keyword
overlap, which captures most of hybrid's grounding benefit cheaply. A true
Postgres FTS leg can be added when VECTOR_BACKEND=pgvector.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from config import get_settings
from embeddings import embed_query

log = logging.getLogger("legally.retrieval")


@dataclass
class RetrievedChunk:
    case_name: str
    citation: str
    court: str
    year: int | None
    outcome: str
    segment_role: str
    chunk_text: str
    similarity_score: float
    chunk_id: str = ""

    def to_dict(self) -> dict:
        return {
            "case_name": self.case_name,
            "citation": self.citation,
            "court": self.court,
            "year": self.year,
            "outcome": self.outcome,
            "segment_role": self.segment_role,
            "chunk_text": self.chunk_text,
            "similarity_score": round(self.similarity_score, 4),
            "chunk_id": self.chunk_id,
        }


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    max_similarity: float = 0.0


# ── Index loading ────────────────────────────────────────────
def _resolve_artifact(local_path: str, hub_filename: str) -> str:
    """Return a readable local path for an index artifact.

    Dev: the file exists under data/ — use it, never touch the network.
    Prod: it's absent, so download the pinned version from the Hub DATASET repo
    (cached after the first call). Pinning to a tag means a deploy can't pick up
    a half-rebuilt index. Raises a clear error if neither is available.
    """
    p = Path(local_path)
    if p.exists():
        return str(p)

    s = get_settings()
    if not s.corpus_repo:
        raise FileNotFoundError(
            f"FAISS artifact not found locally ({local_path}) and no Hub fallback "
            "configured. Either build it offline with pipeline/chunk_embed.py "
            "(brief Phase 0), or set HF_NAMESPACE / CORPUS_REPO to download it."
        )
    from huggingface_hub import hf_hub_download

    log.info("Fetching %s from %s@%s (Hub)…", hub_filename, s.corpus_repo, s.corpus_revision)
    return hf_hub_download(
        repo_id=s.corpus_repo,
        filename=hub_filename,
        revision=s.corpus_revision,
        repo_type="dataset",
    )


@lru_cache
def _load_index():
    """Load the FAISS index + metadata once, cached for the process lifetime."""
    import faiss  # lazy import
    import pandas as pd

    s = get_settings()
    index_path = _resolve_artifact(s.faiss_index_path, s.corpus_index_file)
    meta_path = _resolve_artifact(s.faiss_meta_path, s.corpus_meta_file)
    index = faiss.read_index(str(index_path))
    meta = pd.read_parquet(meta_path)
    log.info("Loaded FAISS index: %d vectors, %d metadata rows", index.ntotal, len(meta))
    return index, meta


_WEIGHT = {"Ratio": 1.25, "Holding": 1.25, "Issues": 1.05}  # boost decisive segments


def _keyword_score(query: str, text: str) -> float:
    """Cheap term-overlap score in [0,1] for the keyword leg of hybrid search."""
    q_terms = set(re.findall(r"[a-z]{3,}", query.lower()))
    if not q_terms:
        return 0.0
    t_terms = set(re.findall(r"[a-z]{3,}", text.lower()))
    return len(q_terms & t_terms) / len(q_terms)


def retrieve(reformulated_query: str, original_query: str, top_k: int | None = None) -> RetrievalResult:
    """Return top-k retrieved chunks for a query.

    Semantic candidates come from FAISS on the reformulated query; we then blend
    in keyword overlap (computed against the ORIGINAL text, per brief §6.2) and a
    rhetorical-role weight that favours Ratio/Holding segments (brief §5).
    """
    s = get_settings()
    k = top_k or s.top_k
    index, meta = _load_index()

    qvec = embed_query(reformulated_query).reshape(1, -1)
    # Over-fetch candidates so the keyword re-rank has something to work with.
    n_candidates = min(max(k * 4, k), index.ntotal)
    sims, idxs = index.search(qvec, n_candidates)  # inner product == cosine (normalized)

    scored: list[tuple[float, float, RetrievedChunk]] = []
    for sim, idx in zip(sims[0], idxs[0]):
        if idx < 0:
            continue
        row = meta.iloc[int(idx)]
        sim = float(sim)
        kw = _keyword_score(original_query, str(row.get("chunk_text", "")))
        role = str(row.get("segment_role", "") or "")
        weight = _WEIGHT.get(role, 1.0)
        blended = (0.75 * sim + 0.25 * kw) * weight
        chunk = RetrievedChunk(
            case_name=str(row.get("case_name", "") or ""),
            citation=str(row.get("citation", "") or ""),
            court=str(row.get("court", "") or ""),
            year=(int(row["year"]) if row.get("year") == row.get("year") and row.get("year") is not None else None),
            outcome=str(row.get("outcome", "") or ""),
            segment_role=role,
            chunk_text=str(row.get("chunk_text", "") or ""),
            similarity_score=sim,
            chunk_id=str(row.get("id", "") or row.name),
        )
        scored.append((blended, sim, chunk))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:k]
    chunks = [c for _, _, c in top]
    max_sim = max((raw for _, raw, _ in top), default=0.0)
    return RetrievalResult(chunks=chunks, max_similarity=max_sim)
