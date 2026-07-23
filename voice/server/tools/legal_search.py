"""Client for the existing Legally AI RAG endpoint, exposed to the voice LLM
as the `legal_search` tool.

Design (context doc §2, §8):
  * The RAG backend is an EXISTING service — we integrate, never rebuild.
  * We call POST /api/retrieve (reformulate + FAISS retrieve, no prediction):
    it returns raw chunks without a nested LLM call, which keeps the tool
    round-trip inside the latency budget and lets the voice LLM compose the
    spoken answer itself.
  * Every call has a hard timeout and a machine-readable failure shape so the
    pipeline can SPEAK a recovery line instead of leaving dead air (§4.8).
  * Results are compacted (top-N chunks, excerpts capped) before they reach the
    LLM so the token budget — and therefore time-to-first-sentence — stays flat
    (§4.9).
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from server.config import get_settings

log = logging.getLogger("legallyai.voice.legal_search")

# One persistent client per process: connection reuse shaves the TCP+TLS
# handshake off every tool call (context doc §3 "warm connections").
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        s = get_settings()
        _client = httpx.AsyncClient(
            base_url=s.rag_base_url,
            timeout=httpx.Timeout(s.rag_timeout_s, connect=2.0),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _compact_chunk(raw: dict, excerpt_chars: int) -> dict:
    """Trim a retrieved chunk to what the LLM actually needs to ground a spoken
    answer. Full text stays available in the post-call summary via chunk_id."""
    text = str(raw.get("chunk_text", "")).strip()
    return {
        "case_name": raw.get("case_name", ""),
        "citation": raw.get("citation", ""),
        "court": raw.get("court", ""),
        "year": raw.get("year"),
        "outcome": raw.get("outcome", ""),
        "excerpt": text[:excerpt_chars] + ("…" if len(text) > excerpt_chars else ""),
        "similarity": raw.get("similarity_score", 0.0),
        "chunk_id": raw.get("chunk_id", ""),
    }


async def legal_search(query: str) -> dict[str, Any]:
    """Retrieve Supreme Court passages relevant to `query`.

    Returns a dict the LLM can ground on:
      ok=True  → {ok, cases, weak_retrieval, max_similarity, latency_ms}
      ok=False → {ok, error, latency_ms}  (the LLM must tell the user retrieval
                 failed and offer to retry — never invent an answer)
    """
    s = get_settings()
    started = time.perf_counter()
    try:
        resp = await _get_client().post("/api/retrieve", json={"question": query})
        resp.raise_for_status()
        data = resp.json()
    except httpx.TimeoutException:
        latency_ms = int((time.perf_counter() - started) * 1000)
        log.warning("legal_search timeout after %dms for query=%r", latency_ms, query)
        return {"ok": False, "error": "timeout", "latency_ms": latency_ms}
    except Exception as e:  # noqa: BLE001 — any failure becomes a spoken recovery
        latency_ms = int((time.perf_counter() - started) * 1000)
        log.warning("legal_search failed after %dms: %s", latency_ms, e)
        return {"ok": False, "error": "unavailable", "latency_ms": latency_ms}

    latency_ms = int((time.perf_counter() - started) * 1000)
    chunks = data.get("chunks", [])[: s.rag_top_chunks]
    max_sim = float(data.get("max_similarity", 0.0))
    result = {
        "ok": True,
        "cases": [_compact_chunk(c, s.rag_excerpt_chars) for c in chunks],
        "weak_retrieval": max_sim < s.rag_weak_similarity,
        "max_similarity": max_sim,
        "latency_ms": latency_ms,
    }
    log.info(
        "legal_search %dms: %d cases, max_sim=%.3f, weak=%s",
        latency_ms, len(result["cases"]), max_sim, result["weak_retrieval"],
    )
    return result
