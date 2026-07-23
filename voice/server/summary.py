"""Post-call text summary with full citations (context doc §2 side channels,
§4.4c: spoken citations stay natural, full citations arrive in writing).

Runs OFF the latency path — generated when the call ends (or on demand from the
UI), so it can afford a normal LLM call and full detail. Uses the same Groq key
as the pipeline via the OpenAI-compatible API, keeping the dependency set flat.
"""
from __future__ import annotations

import logging

import httpx

from server.config import get_settings
from server.llm.dialog_state import DialogState
from server.llm.prompts import SUMMARY_SYSTEM_PROMPT

log = logging.getLogger("legallyai.voice.summary")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


async def build_summary(transcript: list[dict], state: DialogState) -> dict:
    """Return {"summary": str, "citations": [str]} for the finished call.

    `transcript` is [{"role": "user"|"assistant", "content": str}, ...].
    Citations come from the retrieval records in DialogState — the ground truth
    of what was actually retrieved — not from what the LLM said aloud.
    """
    citations: list[str] = []
    for rec in state.retrievals:
        for c in rec.top_citations:
            if c and c not in citations:
                citations.append(c)

    if not transcript:
        return {"summary": "", "citations": citations}

    s = get_settings()
    if not s.groq_api_key:
        return {
            "summary": "(Summary unavailable: GROQ_API_KEY not configured.)",
            "citations": citations,
        }

    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in transcript)
    retrieval_notes = "\n".join(
        f"- search \"{r.query}\": {r.n_cases} cases"
        + (" (weak retrieval)" if r.weak else "")
        + (f" — {'; '.join(c for c in r.top_citations if c)}" if r.top_citations else "")
        for r in state.retrievals
    ) or "(no retrievals were made)"

    user_msg = (
        f"CONVERSATION TRANSCRIPT:\n{convo}\n\n"
        f"RETRIEVAL RECORDS (only permissible source of citations):\n{retrieval_notes}\n\n"
        "Write the post-call summary."
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {s.groq_api_key}"},
                json={
                    "model": s.groq_model,
                    "messages": [
                        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 700,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001 — summary failure must not 500 the call end
        log.error("Summary generation failed: %s", e)
        text = "(Summary could not be generated for this call.)"

    return {"summary": text, "citations": citations}
