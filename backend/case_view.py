"""Reconstruct a full judgment from its indexed chunks, for the "read the whole
case with the cited passage highlighted" view (provenance deep-dive).

The corpus index stores every judgment as ordered chunks in the metadata table.
We filter to one case, restore document order, and flag the chunk that grounded a
citation so the UI can highlight it in context.
"""
from __future__ import annotations

import re

from retrieval import _load_index
from textutil import clean_excerpt


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _order_key(chunk_id: str) -> int:
    # ids look like "{stem}:{global_row}"; the trailing number is document order.
    try:
        return int(str(chunk_id).rsplit(":", 1)[-1])
    except (ValueError, IndexError):
        return 0


def get_case(citation: str = "", case_name: str = "", highlight_id: str = "") -> dict | None:
    _, meta = _load_index()

    cite_n = _norm(citation)
    name_n = _norm(case_name)
    if not cite_n and not name_n:
        return None

    cites = meta["citation"].fillna("").map(_norm)
    names = meta["case_name"].fillna("").map(_norm)
    mask = (cites == cite_n) if cite_n else (names == name_n)
    if cite_n and not mask.any():  # citation missing/blank in meta — fall back to name
        mask = names == name_n
    sub = meta[mask]
    if sub.empty:
        return None

    rows = sorted(
        sub.to_dict("records"),
        key=lambda r: _order_key(r.get("id", "")),
    )
    first = rows[0]
    chunks = []
    for r in rows:
        text = clean_excerpt(str(r.get("chunk_text", "") or ""))
        if not text:
            continue
        chunks.append({
            "text": text,
            "role": str(r.get("segment_role", "") or ""),
            "cited": bool(highlight_id) and str(r.get("id", "")) == str(highlight_id),
        })

    return {
        "case_name": str(first.get("case_name", "") or ""),
        "citation": str(first.get("citation", "") or ""),
        "court": str(first.get("court", "") or ""),
        "year": int(first["year"]) if first.get("year") == first.get("year") and first.get("year") is not None else None,
        "outcome": str(first.get("outcome", "") or ""),
        "n_chunks": len(chunks),
        "chunks": chunks,
    }
