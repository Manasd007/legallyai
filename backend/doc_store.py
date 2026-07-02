"""In-memory store for analyzed documents (text + analysis + chat history).

v1 is per-process and ephemeral — it resets on restart, which matches the
"cached doc context" UX (analyze once, then chat within the session). Swap for
Supabase/Redis when running multiple workers or wanting persistence.
"""
from __future__ import annotations

import time
import uuid

from config import get_settings

_docs: dict[str, dict] = {}


def put(filename: str, text: str, analysis: dict) -> str:
    doc_id = uuid.uuid4().hex[:12]
    _docs[doc_id] = {
        "id": doc_id,
        "filename": filename,
        "text": text,
        "char_count": len(text),
        "analysis": analysis,
        "history": [],  # list of {"role": "user"|"assistant", "content": str}
        "created": time.time(),
    }
    return doc_id


def get(doc_id: str) -> dict | None:
    entry = _docs.get(doc_id)
    if not entry:
        return None
    if time.time() - entry["created"] > get_settings().doc_ttl_seconds:
        _docs.pop(doc_id, None)
        return None
    return entry


def append_turn(doc_id: str, role: str, content: str) -> None:
    entry = _docs.get(doc_id)
    if entry:
        entry["history"].append({"role": role, "content": content})
