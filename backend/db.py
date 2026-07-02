"""Supabase client + persistence helpers (brief §6.6, §8).

Persists cases, predictions, explanations, feedback. Uses the service key
(backend only). Auth/JWT verification of the caller is wired in main.py.
All writes are best-effort in v1: a persistence failure must not break the
user-facing answer (we log and continue).
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache

from config import get_settings

log = logging.getLogger("legally.db")


@lru_cache
def _client():
    from supabase import create_client  # lazy import

    s = get_settings()
    if not s.supabase_url or not s.supabase_service_key:
        raise RuntimeError("Supabase not configured (SUPABASE_URL / SERVICE_KEY).")
    return create_client(s.supabase_url, s.supabase_service_key)


def persist_query(*, user_id: str, raw_text: str, prediction: dict, title: str | None = None) -> str | None:
    """Insert case + prediction + explanation. Returns case_id (or None on failure)."""
    try:
        sb = _client()
        case = (
            sb.table("cases")
            .insert({"user_id": user_id, "raw_text": raw_text, "title": title})
            .execute()
        )
        case_id = case.data[0]["id"]

        pred = (
            sb.table("predictions")
            .insert(
                {
                    "case_id": case_id,
                    "likely_outcome": prediction.get("likely_outcome", "Uncertain"),
                    "confidence": prediction.get("confidence", "low"),
                    "model_version": prediction.get("_model_version", "gemini-rag-v1"),
                }
            )
            .execute()
        )
        prediction_id = pred.data[0]["id"]

        verification = prediction.get("verification", {})
        sb.table("explanations").insert(
            {
                "prediction_id": prediction_id,
                "summary_text": prediction.get("situation_summary", ""),
                "reasoning": prediction.get("reasoning", ""),
                "cited_cases": prediction.get("cited_cases", []),
                "retrieved_ids": verification.get("retrieved_ids", []),
                "method": prediction.get("_model_version", "gemini-rag-v1"),
            }
        ).execute()
        return case_id
    except Exception as e:  # noqa: BLE001 - persistence is best-effort
        log.error("persist_query failed: %s", e)
        return None


def list_history(user_id: str) -> list[dict]:
    try:
        sb = _client()
        return (
            sb.table("cases")
            .select("*, predictions(*)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
            .data
        )
    except Exception as e:  # noqa: BLE001
        log.error("list_history failed: %s", e)
        return []


# ── Conversation threads (returning-user history / "chat sections") ──────────
# These power the sidebar of past sessions. The backend uses the service key, so
# RLS is bypassed; we therefore ALWAYS filter reads by user_id ourselves so one
# user can never reach another's thread.

def _title_from(text: str, limit: int = 60) -> str:
    """A short, human title for a thread, derived from the first user message."""
    t = " ".join((text or "").split())
    return (t[: limit - 1] + "…") if len(t) > limit else (t or "Untitled")


_TITLE_SYSTEM = (
    "You write ultra-short titles for the sidebar of a legal help app. "
    "Given the user's message, reply with a 4-5 word title in Title Case that "
    "names the specific legal issue. No quotes, no ending punctuation, and no "
    "filler words like 'Case', 'Question', or 'Legal'. "
    "Examples: 'Delayed Tax Reassessment Notice', 'Wrongful Dismissal After 12 Years', "
    "'Specific Performance Suit Appeal'. Reply with ONLY the title."
)


def _clean_title(raw: str, max_words: int = 6, max_chars: int = 48) -> str:
    """Sanitize an LLM title: strip quotes/labels/punctuation, cap words & length."""
    t = " ".join((raw or "").split())
    t = t.strip("\"'“”‘’ ")
    t = re.sub(r"^(title|session)\s*[:\-]\s*", "", t, flags=re.IGNORECASE)
    t = t.rstrip(" .,:;—-")
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words])
    return t[:max_chars].rstrip() if len(t) > max_chars else t


def _smart_title(text: str) -> str:
    """A concise 4-5 word title for a thread. Uses the fast intake LLM, and falls
    back to a truncation of the first message on any error (persistence must never
    break the answer path) or for messages already short enough to stand alone."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return "Untitled"
    if len(cleaned) <= 40:  # already title-length; don't spend a call on it
        return cleaned
    try:
        from llm import complete  # lazy: keep persistence import-light

        title = _clean_title(
            complete(
                model=get_settings().router_model,  # fast, cheap Groq intake model
                system=_TITLE_SYSTEM,
                user=cleaned[:600],
                temperature=0.0,
                max_tokens=20,
            )
        )
        return title or _title_from(cleaned)
    except Exception as e:  # noqa: BLE001 - title is a nicety, never fatal
        log.warning("smart title failed, using fallback: %s", e)
        return _title_from(cleaned)


def record_turn(
    *,
    user_id: str,
    conversation_id: str | None,
    tool: str,
    user_text: str,
    assistant_text: str,
    payload: dict | None = None,
    case_id: str | None = None,
    title: str | None = None,
    session_id: str | None = None,
) -> str | None:
    """Append a user→assistant exchange to a thread, creating it on the first turn.

    `session_id` groups the per-tool threads of one workspace session; it's only
    used when the thread is first created. Returns the conversation_id so the
    client can keep the thread going. Entirely best-effort: a persistence failure
    must never break the user-facing answer.
    """
    try:
        sb = _client()
        if not conversation_id:
            conv = (
                sb.table("conversations")
                .insert(
                    {
                        "user_id": user_id,
                        "tool": tool,
                        "session_id": session_id,
                        "title": title or _smart_title(user_text),
                    }
                )
                .execute()
            )
            conversation_id = conv.data[0]["id"]
        else:
            # Make sure the caller owns this thread before appending to it.
            owned = (
                sb.table("conversations")
                .select("id")
                .eq("id", conversation_id)
                .eq("user_id", user_id)
                .execute()
            )
            if not owned.data:
                log.warning("record_turn: conversation %s not owned by %s", conversation_id, user_id)
                return None

        rows = [
            {"conversation_id": conversation_id, "role": "user", "content": user_text},
            {
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": assistant_text,
                "payload": payload,
                "case_id": case_id,
            },
        ]
        sb.table("messages").insert(rows).execute()
        # Bump updated_at so the sidebar sorts this thread to the top. Send an
        # ISO timestamp (PostgREST passes it through as a literal — "now()" would
        # be stored as the string, not evaluated).
        from datetime import datetime, timezone

        sb.table("conversations").update(
            {"updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()
        return conversation_id
    except Exception as e:  # noqa: BLE001 - persistence is best-effort
        log.error("record_turn failed: %s", e)
        return conversation_id


def list_conversations(user_id: str) -> list[dict]:
    """Sidebar list: most-recently-active threads first."""
    try:
        return (
            _client()
            .table("conversations")
            .select("id, tool, title, created_at, updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(100)
            .execute()
            .data
        )
    except Exception as e:  # noqa: BLE001
        log.error("list_conversations failed: %s", e)
        return []


def get_conversation(*, user_id: str, conversation_id: str) -> dict | None:
    """Full thread (header + ordered messages), or None if not found/owned."""
    try:
        sb = _client()
        conv = (
            sb.table("conversations")
            .select("*")
            .eq("id", conversation_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not conv.data:
            return None
        messages = (
            sb.table("messages")
            .select("id, role, content, payload, case_id, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
            .data
        )
        return {"conversation": conv.data[0], "messages": messages}
    except Exception as e:  # noqa: BLE001
        log.error("get_conversation failed: %s", e)
        return None


# ── Sessions (the workspace-level grouping of per-tool threads) ──────────────
# One session bundles up to three threads (predict/documents, assistant,
# statutes) under a shared session_id. The sidebar lists sessions, not raw
# threads, so a single matter shows as one entry. Legacy rows (session_id null)
# are surfaced as singleton sessions keyed by their own conversation id.

def list_sessions(user_id: str) -> list[dict]:
    """Sidebar list: one entry per workspace session, most-recently-active first."""
    try:
        rows = (
            _client()
            .table("conversations")
            .select("id, tool, title, session_id, created_at, updated_at")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(300)
            .execute()
            .data
        )
    except Exception as e:  # noqa: BLE001
        log.error("list_sessions failed: %s", e)
        return []

    groups: dict[str, dict] = {}
    for r in rows:
        key = r.get("session_id") or r["id"]
        g = groups.get(key)
        if g is None:
            groups[key] = {
                "session_id": key,
                "title": r.get("title") or "Untitled",
                "title_at": r.get("created_at") or "",
                "updated_at": r.get("updated_at") or "",
                "tools": {r["tool"]},
                "conversation_count": 1,
            }
            continue
        g["conversation_count"] += 1
        g["tools"].add(r["tool"])
        if (r.get("updated_at") or "") > g["updated_at"]:
            g["updated_at"] = r["updated_at"]
        # Title comes from the *earliest* thread in the session (the matter as
        # first described). Rows arrive newest-first, so an older one wins.
        if (r.get("created_at") or "") < g["title_at"]:
            g["title"] = r.get("title") or g["title"]
            g["title_at"] = r.get("created_at") or g["title_at"]

    out = [
        {
            "session_id": g["session_id"],
            "title": g["title"],
            "updated_at": g["updated_at"],
            "tools": sorted(g["tools"]),
            "conversation_count": g["conversation_count"],
        }
        for g in groups.values()
    ]
    out.sort(key=lambda g: g["updated_at"], reverse=True)
    return out


def get_session(*, user_id: str, session_id: str) -> dict | None:
    """Every thread in a session, each with its ordered messages, for rehydration.

    Accepts either a real session_id or a bare conversation id (legacy singleton
    sessions). Returns None if nothing the caller owns matches.
    """
    try:
        sb = _client()
        convs = (
            sb.table("conversations")
            .select("id, tool, title, session_id, created_at")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .order("created_at")
            .execute()
            .data
        )
        # Fall back to a singleton (legacy rows have no session_id).
        if not convs:
            one = (
                sb.table("conversations")
                .select("id, tool, title, session_id, created_at")
                .eq("user_id", user_id)
                .eq("id", session_id)
                .execute()
                .data
            )
            if not one:
                return None
            convs = one

        conversations = []
        for c in convs:
            messages = (
                sb.table("messages")
                .select("id, role, content, payload, case_id, created_at")
                .eq("conversation_id", c["id"])
                .order("created_at")
                .execute()
                .data
            )
            conversations.append({**c, "messages": messages})

        title = conversations[0].get("title") or "Untitled"
        return {"session_id": session_id, "title": title, "conversations": conversations}
    except Exception as e:  # noqa: BLE001
        log.error("get_session failed: %s", e)
        return None


def add_feedback(*, user_id: str, prediction_id: str, rating: int, note: str | None) -> bool:
    try:
        _client().table("feedback").insert(
            {"user_id": user_id, "prediction_id": prediction_id, "rating": rating, "note": note}
        ).execute()
        return True
    except Exception as e:  # noqa: BLE001
        log.error("add_feedback failed: %s", e)
        return False
