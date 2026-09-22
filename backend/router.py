from __future__ import annotations

import json
import logging
from typing import Literal, TypedDict

from config import get_settings, load_prompt
from llm import complete
from textutil import is_smalltalk

log = logging.getLogger("legally.router")

Category = Literal["legal", "general_legal", "not_legal"]


class RouteResult(TypedDict):
    category: Category
    topic: str | None


def _safe_parse(text: str) -> RouteResult:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(text)
        cat = data.get("category")
        if cat not in ("legal", "general_legal", "not_legal"):
            raise ValueError(f"bad category: {cat!r}")
        return {"category": cat, "topic": data.get("topic")}
    except Exception as e:  # noqa: BLE001
        log.warning("Router parse failed (%s); defaulting to 'legal'", e)
        return {"category": "legal", "topic": None}


def classify(question: str) -> RouteResult:
    if is_smalltalk(question):
        return {"category": "not_legal", "topic": None}
    prompt = load_prompt("router_v2.txt")
    try:
        out = complete(
            model=get_settings().router_model,
            system=prompt,
            user=question,
            temperature=0.0,
            json_mode=True,
            max_tokens=512,
            reasoning_effort="low",
            seed=get_settings().llm_seed,
        )
        return _safe_parse(out)
    except Exception as e:  # noqa: BLE001
        log.warning("Router LLM failed (%s); defaulting to 'legal'", e)
        return {"category": "legal", "topic": None}
