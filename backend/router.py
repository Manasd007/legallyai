"""Intake router: classify legal / general_legal / not_legal (brief §6.1).

Single fast Groq call returning JSON. Wired into /api/query's request flow
in main.py; /api/retrieve bypasses it for direct reformulate+retrieve debugging.
"""
from __future__ import annotations

import json
import logging
from typing import Literal, TypedDict

from config import get_settings, load_prompt
from llm import complete

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
        # Fail OPEN to the legal path: better to attempt grounded retrieval than
        # to wrongly decline a real legal question. Retrieval + verification will
        # still hedge if nothing relevant is found.
        return {"category": "legal", "topic": None}


def classify(question: str) -> RouteResult:
    prompt = load_prompt("router_v2.txt")
    try:
        out = complete(
            model=get_settings().router_model,
            system=prompt,
            user=question,
            temperature=0.0,
            json_mode=True,
            max_tokens=120,
        )
        return _safe_parse(out)
    except Exception as e:  # noqa: BLE001
        log.warning("Router LLM failed (%s); defaulting to 'legal'", e)
        return {"category": "legal", "topic": None}
