"""LLM provider abstraction with fallback (brief §4, §9).

Uses LiteLLM as a single interface to Groq / Gemini / OpenRouter so model IDs
are just strings from config. On a provider/rate-limit error, we fail over to
the configured fallback model before giving up — a legal answer path should
never die with a bare 500 (brief §6.4).
"""
from __future__ import annotations

import logging

from config import get_settings

log = logging.getLogger("legally.llm")

try:
    import litellm  # type: ignore

    # Surface only real errors; LiteLLM is chatty by default.
    litellm.suppress_debug_info = True
except Exception:  # pragma: no cover - import guard for skeleton/dev envs
    litellm = None


class LLMError(RuntimeError):
    """Raised when both primary and fallback providers fail."""


def _api_key_for(model: str) -> dict:
    """Map a model id prefix to the right key kwarg for LiteLLM."""
    s = get_settings()
    if model.startswith("groq/"):
        return {"api_key": s.groq_api_key}
    if model.startswith("gemini/"):
        return {"api_key": s.google_api_key}
    if model.startswith("openrouter/"):
        return {"api_key": s.openrouter_api_key}
    return {}


def complete(
    *,
    model: str,
    system: str | None,
    user: str,
    temperature: float = 0.2,
    json_mode: bool = False,
    max_tokens: int | None = None,
) -> str:
    """Single-turn completion. Returns the assistant message text.

    Falls back to settings.fallback_model on any exception from the primary.
    """
    if litellm is None:
        raise LLMError(
            "litellm is not installed. `pip install litellm` to enable LLM calls."
        )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    kwargs: dict = {"temperature": temperature}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    s = get_settings()
    candidates = [model, s.fallback_model]
    last_err: Exception | None = None

    for candidate in candidates:
        try:
            resp = litellm.completion(
                model=candidate,
                messages=messages,
                **_api_key_for(candidate),
                **kwargs,
            )
            return resp["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - we deliberately try the fallback
            log.warning("LLM call failed on %s: %s", candidate, e)
            last_err = e
            continue

    raise LLMError(f"All LLM providers failed; last error: {last_err}")
