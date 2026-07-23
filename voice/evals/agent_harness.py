"""Text-level agent harness for evals.

Runs the SAME system prompt, tool schema and legal_search client as the voice
pipeline, but over plain text turns via Groq's OpenAI-compatible API — no audio,
no Pipecat. This is what lets grounding/refusal/context evals (context doc §6)
run in CI without microphones: the voice layer changes how turns arrive, not
what the LLM is allowed to say.
"""
from __future__ import annotations

import json
import logging

import httpx

from server.config import get_settings
from server.llm.dialog_state import DialogState, trim_history
from server.llm.prompts import LEGAL_SEARCH_DESCRIPTION, SYSTEM_PROMPT
from server.tools.legal_search import legal_search

log = logging.getLogger("legallyai.voice.evals.harness")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "legal_search",
            "description": LEGAL_SEARCH_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Self-contained English description of the legal issue.",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


class AgentHarness:
    """One simulated conversation: turn-in, spoken-style answer out."""

    def __init__(self) -> None:
        self.state = DialogState(session_id="eval")
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tool_queries: list[str] = []
        self.retrieved: list[dict] = []  # every case returned by any tool call
        self.last_weak: bool = False

    async def turn(self, user_text: str, max_tool_rounds: int = 2) -> str:
        s = get_settings()
        self.state.note_user_turn(user_text)
        state_block = self.state.render()
        content = f"{state_block}\n\n{user_text}" if state_block else user_text
        self.messages.append({"role": "user", "content": content})

        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(max_tool_rounds + 1):
                resp = await client.post(
                    GROQ_CHAT_URL,
                    headers={"Authorization": f"Bearer {s.groq_api_key}"},
                    json={
                        "model": s.groq_model,
                        "messages": trim_history(self.messages),
                        "tools": TOOLS,
                        "temperature": 0.2,
                        "max_tokens": 300,
                    },
                )
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]

                if not msg.get("tool_calls"):
                    answer = (msg.get("content") or "").strip()
                    self.messages.append({"role": "assistant", "content": answer})
                    self.state.note_agent_turn(answer)
                    return answer

                self.messages.append(msg)
                for tc in msg["tool_calls"]:
                    try:
                        query = json.loads(tc["function"]["arguments"]).get("query", "")
                    except (json.JSONDecodeError, KeyError):
                        query = ""
                    self.tool_queries.append(query)
                    result = await legal_search(query)
                    self.state.note_tool_call(query, result)
                    self.last_weak = bool(result.get("weak_retrieval"))
                    if result.get("ok"):
                        self.retrieved.extend(result["cases"])
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
        return "(no final answer after tool rounds)"
