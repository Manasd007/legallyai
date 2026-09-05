from __future__ import annotations

import logging
from dataclasses import dataclass, field

from config import get_settings
from retrieval import RetrievalResult, RetrievedChunk

log = logging.getLogger("legally.assembly")

_SUPPORTING_PRIORITY = {"Ratio": 0, "Holding": 1, "Issues": 2, "Facts": 3}
_SUPPORTING_MAX_CHARS = 700


@dataclass
class CaseBundle:
    case_name: str
    citation: str
    court: str
    year: int | None
    outcome: str
    primary: RetrievedChunk
    supporting: list[RetrievedChunk] = field(default_factory=list)


def _case_key(chunk: RetrievedChunk) -> str:
    cid = chunk.chunk_id or ""
    if ":" in cid:
        return cid.rsplit(":", 1)[0]
    return (chunk.citation or chunk.case_name).strip().lower()


def _fetch_supporting(key: str, exclude_ids: set[str], limit: int) -> list[RetrievedChunk]:
    if limit <= 0:
        return []
    try:
        from retrieval import _load_index, _row_to_chunk

        _, meta = _load_index()
        ids = meta["id"].astype(str)
        mask = ids.str.startswith(key + ":") if key else ids.isin([])
        rows = [i for i in meta.index[mask].tolist() if str(meta.iloc[i].get("id", "")) not in exclude_ids]
        chunks = [_row_to_chunk(meta, i, 0.0) for i in rows]
        chunks.sort(key=lambda c: _SUPPORTING_PRIORITY.get(c.segment_role, 9))
        return chunks[:limit]
    except Exception as e:  # noqa: BLE001 - supporting context is best-effort
        log.warning("Supporting-segment fetch failed for %s (%s).", key, e)
        return []


def assemble(result: RetrievalResult) -> list[CaseBundle]:
    s = get_settings()
    order: list[str] = []
    groups: dict[str, list[RetrievedChunk]] = {}
    for c in result.chunks:
        key = _case_key(c)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)

    bundles: list[CaseBundle] = []
    for key in order:
        hits = groups[key]
        primary = hits[0]
        exclude = {h.chunk_id for h in hits}
        supporting = list(hits[1:])
        if s.case_assembly_enabled:
            need = s.case_max_supporting - len(supporting)
            if need > 0:
                supporting += _fetch_supporting(key, exclude, need)
        supporting = supporting[: s.case_max_supporting]
        bundles.append(
            CaseBundle(
                case_name=primary.case_name,
                citation=primary.citation,
                court=primary.court,
                year=primary.year,
                outcome=primary.outcome,
                primary=primary,
                supporting=supporting,
            )
        )
    return bundles


def _seg(chunk: RetrievedChunk, cap: int) -> str:
    from textutil import clean_excerpt

    text = clean_excerpt(chunk.chunk_text or "")
    if len(text) > cap:
        text = text[:cap].rstrip() + "…"
    return text


def format_context(result: RetrievalResult) -> str:
    bundles = assemble(result)
    if not bundles:
        return "(no documents retrieved)"
    parts = []
    for i, b in enumerate(bundles, 1):
        block = [
            f"[{i}] case_name: {b.case_name}",
            f"    citation: {b.citation}",
            f"    court/year: {b.court} {b.year or ''}".rstrip(),
            f"    recorded_outcome: {b.outcome}",
            f"    matched segment ({b.primary.segment_role}): {_seg(b.primary, 1200)}",
        ]
        for sup in b.supporting:
            block.append(f"    also from this case ({sup.segment_role}): {_seg(sup, _SUPPORTING_MAX_CHARS)}")
        parts.append("\n".join(block))
    return "\n\n".join(parts)
