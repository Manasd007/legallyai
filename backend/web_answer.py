from __future__ import annotations

import logging

from config import get_settings, load_prompt
from llm import complete
import web_search

log = logging.getLogger("legally.webanswer")


def answer(question: str) -> dict:
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
            max_tokens=1200,
            reasoning_effort="low",
        ).strip()
    except Exception as e:  # noqa: BLE001
        log.error("Web answer synthesis failed: %s", e)
        text = None

    return {"answer": text, "sources": sources}
