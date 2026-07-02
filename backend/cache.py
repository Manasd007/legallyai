"""Query result cache (brief §16).

Free LLM tiers cap throughput, so repeated/similar queries should hit a cache
keyed on the reformulated query. v1 uses a simple in-process TTL dict; swap for
Redis/Supabase when running multiple workers.
"""
from __future__ import annotations

import hashlib
import time

from config import get_settings

_store: dict[str, tuple[float, dict]] = {}


def _key(reformulated_query: str) -> str:
    return hashlib.sha256(reformulated_query.strip().lower().encode()).hexdigest()


def get(reformulated_query: str) -> dict | None:
    entry = _store.get(_key(reformulated_query))
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > get_settings().cache_ttl_seconds:
        _store.pop(_key(reformulated_query), None)
        return None
    return value


def set(reformulated_query: str, value: dict) -> None:
    _store[_key(reformulated_query)] = (time.time(), value)


def clear() -> None:
    _store.clear()
