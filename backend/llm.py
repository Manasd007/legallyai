from __future__ import annotations

import logging

from config import get_settings

log = logging.getLogger("legally.llm")

try:
    import litellm  # type: ignore

    litellm.suppress_debug_info = True
except Exception:  # pragma: no cover - import guard for skeleton/dev envs
    litellm = None


class LLMError(RuntimeError):
    pass


def _api_key_for(model: str) -> dict:
    s = get_settings()
    if model.startswith("groq/"):
        return {"api_key": s.groq_api_key}
    if model.startswith("gemini/"):
        return {"api_key": s.google_api_key}
    if model.startswith("openrouter/"):
        return {"api_key": s.openrouter_api_key}
    return {}


def _target_for(model: str) -> tuple[str, dict]:
    s = get_settings()
    if s.conduit_base_url:
        conduit_model = (
            s.conduit_model_map.get(model)
            or s.conduit_model_map.get(model.split("/", 1)[0])
            or s.conduit_default_model
        )
        return (
            f"openai/{conduit_model}",
            {"api_base": s.conduit_base_url, "api_key": s.conduit_api_key},
        )
    return model, _api_key_for(model)


def complete(
    *,
    model: str,
    system: str | None,
    user: str,
    temperature: float = 0.2,
    json_mode: bool = False,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> str:
    if litellm is None:
        raise LLMError(
            "litellm is not installed. `pip install litellm` to enable LLM calls."
        )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    kwargs: dict = {"temperature": temperature, "num_retries": 2}
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort

    s = get_settings()
    candidates = [model, s.fallback_model]
    last_err: Exception | None = None

    for candidate in candidates:
        target, target_kwargs = _target_for(candidate)
        try:
            resp = litellm.completion(
                model=target,
                messages=messages,
                **target_kwargs,
                **kwargs,
            )
            return resp["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001 - we deliberately try the fallback
            log.warning("LLM call failed on %s (via %s): %s", candidate, target, e)
            last_err = e
            continue

    raise LLMError(f"All LLM providers failed; last error: {last_err}")
