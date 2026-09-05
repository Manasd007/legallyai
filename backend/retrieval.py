from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

import lexical
import rerank
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
    rerank_score: float | None = None

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
            "rerank_score": round(self.rerank_score, 4) if self.rerank_score is not None else None,
            "chunk_id": self.chunk_id,
        }


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    max_similarity: float = 0.0


def _resolve_artifact(local_path: str, hub_filename: str) -> str:
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
    import faiss
    import pandas as pd

    s = get_settings()
    index_path = _resolve_artifact(s.faiss_index_path, s.corpus_index_file)
    meta_path = _resolve_artifact(s.faiss_meta_path, s.corpus_meta_file)
    index = faiss.read_index(str(index_path))
    meta = pd.read_parquet(meta_path)
    log.info("Loaded FAISS index: %d vectors, %d metadata rows", index.ntotal, len(meta))
    return index, meta


_WEIGHT = {"Ratio": 1.25, "Holding": 1.25, "Issues": 1.05}


def _rrf(rankings: list[list[int]], weights: list[float], k: int) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking, w in zip(rankings, weights):
        for rank, row in enumerate(ranking):
            scores[row] = scores.get(row, 0.0) + w / (k + rank + 1)
    return scores


def _row_to_chunk(meta, row: int, cosine: float) -> RetrievedChunk:
    r = meta.iloc[row]
    year = r.get("year")
    return RetrievedChunk(
        case_name=str(r.get("case_name", "") or ""),
        citation=str(r.get("citation", "") or ""),
        court=str(r.get("court", "") or ""),
        year=(int(year) if year is not None and year == year else None),
        outcome=str(r.get("outcome", "") or ""),
        segment_role=str(r.get("segment_role", "") or ""),
        chunk_text=str(r.get("chunk_text", "") or ""),
        similarity_score=cosine,
        chunk_id=str(r.get("id", "") or r.name),
    )


def retrieve(reformulated_query: str, original_query: str, top_k: int | None = None) -> RetrievalResult:
    s = get_settings()
    k = top_k or s.top_k
    index, meta = _load_index()

    qvec = embed_query(reformulated_query).reshape(1, -1)
    n_cand = min(max(s.hybrid_candidates, k), index.ntotal)
    sims, idxs = index.search(qvec, n_cand)
    dense_order = [int(i) for i in idxs[0] if i >= 0]
    dense_cos = {int(i): float(sc) for sc, i in zip(sims[0], idxs[0]) if i >= 0}

    lex_order: list[int] = []
    if s.retrieval_mode == "hybrid":
        lex_query = f"{original_query} {reformulated_query}".strip()
        lex_order = [row for row, _ in lexical.search(lex_query, n_cand)]

    fused = _rrf([dense_order, lex_order], [s.dense_weight, s.lexical_weight], s.rrf_k)
    if not fused:
        return RetrievalResult(chunks=[], max_similarity=0.0)

    for row in list(fused):
        role = str(meta.iloc[row].get("segment_role", "") or "")
        fused[row] *= _WEIGHT.get(role, 1.0)

    ranked = sorted(fused, key=lambda r: fused[r], reverse=True)[:s.rerank_candidates]

    qflat = qvec[0]

    def cosine(row: int) -> float:
        if row in dense_cos:
            return dense_cos[row]
        try:
            return float(np.dot(qflat, index.reconstruct(int(row))))
        except Exception:  # noqa: BLE001
            return 0.0

    cand = [_row_to_chunk(meta, row, cosine(row)) for row in ranked]

    scores = rerank.score_pairs(reformulated_query, [c.chunk_text for c in cand])
    if scores is not None:
        for c, sc in zip(cand, scores):
            c.rerank_score = float(sc)
        cand.sort(key=lambda c: c.rerank_score, reverse=True)

    top = cand[:k]
    max_sim = max((c.similarity_score for c in top), default=0.0)
    return RetrievalResult(chunks=top, max_similarity=max_sim)
