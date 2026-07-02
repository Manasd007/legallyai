"""Conversation-aware intake for the chat path.

Decides how to handle the latest user turn so we don't force case retrieval (or a
web search) onto greetings, small talk, or questions about the assistant itself.

Modes:
  - "smalltalk": greeting / chit-chat / meta / off-topic → short friendly reply.
  - "general":   conceptual legal question → answer from general knowledge, no
                 specific case citations.
  - "case_law":  needs grounding in retrieved Supreme Court cases.

A single fast Groq call returning JSON. Fails open to "case_law" (grounding is the
safe default for anything that might be a real legal question)."""
from __future__ import annotations

import json
import logging
from typing import Literal

from config import get_settings, load_prompt
from llm import complete

log = logging.getLogger("legally.chat_intake")

Mode = Literal["smalltalk", "general", "case_law"]
_VALID: set[str] = {"smalltalk", "general", "case_law"}


def _convo(history: list[dict], limit: int = 6) -> str:
    turns = history[-limit:]
    if not turns:
        return "(none)"
    return "\n".join(f"{h.get('role', 'user').upper()}: {h.get('content', '')}" for h in turns)


def classify(question: str, history: list[dict] | None = None) -> Mode:
    history = history or []
    user = f"CONVERSATION SO FAR:\n{_convo(history)}\n\nLATEST MESSAGE: {question}"
    try:
        out = complete(
            model=get_settings().router_model,
            system=load_prompt("chat_intake_v1.txt"),
            user=user,
            temperature=0.0,
            json_mode=True,
            max_tokens=40,
        )
        text = out.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        mode = json.loads(text).get("mode")
        if mode in _VALID:
            return mode  # type: ignore[return-value]
        log.warning("chat intake: bad mode %r; defaulting to case_law", mode)
    except Exception as e:  # noqa: BLE001
        log.warning("chat intake failed (%s); defaulting to case_law", e)
    return "case_law"
