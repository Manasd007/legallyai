"""Grounded predict + explain — single LLM call (brief §6.4).

Returns the structured JSON contract. Robust to malformed JSON: parse, retry
once with a "valid JSON only" reminder, then fall back to an Uncertain hedge.
Citation verification (verify.py) runs AFTER this, on the returned cited_cases.
"""
from __future__ import annotations

import json
import logging

from config import get_settings, load_prompt
from llm import complete
from retrieval import RetrievalResult

log = logging.getLogger("legally.predict")

MODEL_VERSION = "gemini-rag-v2"

_VALID_OUTCOMES = {"Granted", "Dismissed", "Uncertain"}
_VALID_CONFIDENCE = {"low", "medium", "high"}


def _format_context(result: RetrievalResult) -> str:
    """Render retrieved chunks into a numbered, citation-tagged block."""
    parts = []
    for i, c in enumerate(result.chunks, 1):
        parts.append(
            f"[{i}] case_name: {c.case_name}\n"
            f"    citation: {c.citation}\n"
            f"    court/year: {c.court} {c.year or ''}\n"
            f"    recorded_outcome: {c.outcome}\n"
            f"    segment ({c.segment_role}): {c.chunk_text}"
        )
    return "\n\n".join(parts) if parts else "(no documents retrieved)"


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t[3:]
        t = t.removeprefix("json").strip().removesuffix("```").strip()
    return t


def _normalize(data: dict) -> dict:
    outcome = data.get("likely_outcome", "Uncertain")
    if outcome not in _VALID_OUTCOMES:
        outcome = "Uncertain"
    conf = data.get("confidence", "low")
    if conf not in _VALID_CONFIDENCE:
        conf = "low"
    cited = data.get("cited_cases") or []
    if not isinstance(cited, list):
        cited = []

    factors = []
    for f in (data.get("key_factors") or []):
        if not isinstance(f, dict):
            continue
        assessment = str(f.get("assessment", "unclear")).lower()
        if assessment not in ("favorable", "unfavorable", "unclear"):
            assessment = "unclear"
        factor = str(f.get("factor", "")).strip()
        if factor:
            factors.append({
                "factor": factor,
                "assessment": assessment,
                "reason": str(f.get("reason", "")).strip(),
            })

    strengthen = [str(x).strip() for x in (data.get("what_would_strengthen") or []) if str(x).strip()]

    return {
        "situation_summary": str(data.get("situation_summary", "")),
        "likely_outcome": outcome,
        "confidence": conf,
        "reasoning": str(data.get("reasoning", "")),
        "key_factors": factors,
        "what_would_strengthen": strengthen,
        "cited_cases": [
            {
                "case_name": str(c.get("case_name", "")),
                "citation": str(c.get("citation", "")),
                "relevance": str(c.get("relevance", "")),
            }
            for c in cited
            if isinstance(c, dict)
        ],
    }


def _uncertain_fallback(summary: str = "") -> dict:
    return {
        "situation_summary": summary,
        "likely_outcome": "Uncertain",
        "confidence": "low",
        "reasoning": (
            "I could not produce a reliable structured prediction for this "
            "situation from the retrieved material."
        ),
        "key_factors": [],
        "what_would_strengthen": [],
        "cited_cases": [],
    }


def predict(reformulated_query: str, original_question: str, result: RetrievalResult) -> dict:
    system = load_prompt("predict_system_v2.txt")
    context = _format_context(result)
    user = (
        load_prompt("predict_user_v2.txt")
        .replace("{reformulated_query}", reformulated_query)
        .replace("{original_question}", original_question)
        .replace("{retrieved_context}", context)
    )

    model = get_settings().reasoning_model
    for attempt in range(2):
        try:
            raw = complete(
                model=model,
                system=system,
                user=user if attempt == 0 else user + "\n\nReturn VALID JSON ONLY.",
                temperature=0.25,
                json_mode=True,
                max_tokens=1200,
            )
            data = json.loads(_strip_fences(raw))
            return _normalize(data)
        except json.JSONDecodeError as e:
            log.warning("Prediction JSON parse failed (attempt %d): %s", attempt + 1, e)
            continue
        except Exception as e:  # noqa: BLE001 - provider/rate-limit etc.
            log.error("Prediction call failed: %s", e)
            break

    return _uncertain_fallback()
