"""Keyless web search (DuckDuckGo) for the graceful out-of-scope fallback.

When a question is outside Legally AI's legal scope we don't dead-end the user —
we run a quick web search so the model can summarise real results with links.
Degrades to [] on any failure so the caller can fall back further.
"""
from __future__ import annotations

import logging

log = logging.getLogger("legally.web")


def search(query: str, n: int = 5) -> list[dict]:
    try:
        from ddgs import DDGS

        out: list[dict] = []
        for r in DDGS().text(query, max_results=n):
            out.append({
                "title": (r.get("title") or "").strip(),
                "snippet": (r.get("body") or "").strip(),
                "url": (r.get("href") or "").strip(),
            })
        return [r for r in out if r["snippet"] or r["title"]]
    except Exception as e:  # noqa: BLE001 - search is best-effort
        log.warning("Web search failed: %s", e)
        return []
