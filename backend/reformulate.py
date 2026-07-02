"""Query reformulation: layperson situation -> legal-issue statement (brief §6.2).

Improves retrieval because dense judgment text and plain descriptions embed
poorly against each other. On any LLM failure we degrade gracefully to the
original question rather than failing the request.
"""
from __future__ import annotations

import logging

from config import get_settings, load_prompt
from llm import complete

log = logging.getLogger("legally.reformulate")


def reformulate(question: str) -> str:
    system = load_prompt("reformulate_v2.txt")
    try:
        out = complete(
            model=get_settings().reformulate_model,
            system=system,
            user=question,
            temperature=0.2,
            max_tokens=400,
        )
        out = out.strip()
        return out or question
    except Exception as e:  # noqa: BLE001 - reformulation is best-effort
        log.warning("Reformulation failed, using original question: %s", e)
        return question
