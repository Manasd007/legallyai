from __future__ import annotations

import logging

import cache
from config import get_settings, load_prompt
from llm import complete
from textutil import normalize_query

log = logging.getLogger("legally.reformulate")


def reformulate(question: str) -> str:
    ck = "reform|" + normalize_query(question)
    hit = cache.get(ck)
    if hit and hit.get("q"):
        return hit["q"]

    system = load_prompt("reformulate_v2.txt")
    try:
        out = complete(
            model=get_settings().reformulate_model,
            system=system,
            user=question,
            temperature=0.0,
            max_tokens=600,
            reasoning_effort="low",
            seed=get_settings().llm_seed,
        )
        out = (out or "").strip() or question
    except Exception as e:  # noqa: BLE001 - reformulation is best-effort
        log.warning("Reformulation failed, using original question: %s", e)
        return question

    cache.set(ck, {"q": out})
    return out
