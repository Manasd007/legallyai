"""Graceful out-of-scope answer: web search + LLM summary with source links.

Used when the router classifies a question as non-legal — instead of dead-ending
the user, we search the web and summarise the real results, clearly framed as
general info (not legal advice) with citations the user can click through.
"""
from __future__ import annotations

import logging

from config import get_settings, load_prompt
from llm import complete
import web_search

log = logging.getLogger("legally.webanswer")


def answer(question: str) -> dict:
    """Return {"answer": str|None, "sources": [{title,snippet,url}]}."""
    sources = web_search.search(question, n=5)
    if not sources:
        return {"answer": None, "sources": []}

    context = "\n\n".join(
        f"[{i}] {r['title']}\n{r['snippet']}\n{r['url']}" for i, r in enumerate(sources, 1)
    )
    system = load_prompt("web_answer_system_v1.txt")
    user = f"WEB RESULTS:\n{context}\n\nQUESTION: {question}\n\nAnswer using the results, citing [n]."

    try:
        text = complete(
            model=get_settings().reasoning_model,
            system=system,
            user=user,
            temperature=0.3,
            max_tokens=600,
        ).strip()
    except Exception as e:  # noqa: BLE001
        log.error("Web answer synthesis failed: %s", e)
        text = None

    return {"answer": text, "sources": sources}
