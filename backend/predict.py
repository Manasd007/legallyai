from __future__ import annotations

import json
import logging

import context_assembly
from config import get_settings, load_prompt
from llm import complete
from retrieval import RetrievalResult
import validator as validator_mod

log = logging.getLogger("legally.predict")

MODEL_VERSION = "gemini-rag-v2"

_VALID_OUTCOMES = {"Granted", "Dismissed", "Uncertain"}
_VALID_CONFIDENCE = {"low", "medium", "high"}


def _format_context(result: RetrievalResult) -> str:
    try:
        return context_assembly.format_context(result)
    except Exception as e:  # noqa: BLE001 - never fail prediction on formatting
        log.warning("Case assembly failed (%s); using flat chunk context.", e)
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
    from textutil import normalize_text as _n
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
        factor = _n(str(f.get("factor", "")).strip())
        if factor:
            factors.append({
                "factor": factor,
                "assessment": assessment,
                "reason": _n(str(f.get("reason", "")).strip()),
            })

    strengthen = [_n(str(x).strip()) for x in (data.get("what_would_strengthen") or []) if str(x).strip()]

    return {
        "situation_summary": _n(str(data.get("situation_summary", ""))),
        "likely_outcome": outcome,
        "confidence": conf,
        "reasoning": _n(str(data.get("reasoning", ""))),
        "key_factors": factors,
        "what_would_strengthen": strengthen,
        "cited_cases": [
            {
                "case_name": str(c.get("case_name", "")),
                "citation": str(c.get("citation", "")),
                "relevance": _n(str(c.get("relevance", ""))),
            }
            for c in cited
            if isinstance(c, dict)
        ],
    }


_FALLBACK_REASONING = (
    "I could not produce a reliable structured prediction for this "
    "situation from the retrieved material."
)


def _uncertain_fallback(summary: str = "") -> dict:
    return {
        "situation_summary": summary,
        "likely_outcome": "Uncertain",
        "confidence": "low",
        "reasoning": _FALLBACK_REASONING,
        "key_factors": [],
        "what_would_strengthen": [],
        "cited_cases": [],
    }


def _render_draft(prediction: dict) -> str:
    lines = [
        f"Likely outcome: {prediction.get('likely_outcome')}",
        f"Stated confidence: {prediction.get('confidence')}",
        f"Reasoning: {prediction.get('reasoning')}",
    ]
    factors = prediction.get("key_factors") or []
    if factors:
        lines.append("Key factors:")
        for f in factors:
            lines.append(
                f"  - {f.get('factor')} [{f.get('assessment')}]: {f.get('reason')}"
            )
    cited = prediction.get("cited_cases") or []
    if cited:
        lines.append("Cases relied on:")
        for c in cited:
            lines.append(
                f"  - {c.get('case_name')} ({c.get('citation')}): {c.get('relevance')}"
            )
    return "\n".join(lines)


def predict(
    reformulated_query: str,
    original_question: str,
    result: RetrievalResult,
    feedback: str | None = None,
) -> dict:
    system = load_prompt("predict_system_v2.txt")
    context = _format_context(result)
    user = (
        load_prompt("predict_user_v2.txt")
        .replace("{reformulated_query}", reformulated_query)
        .replace("{original_question}", original_question)
        .replace("{retrieved_context}", context)
    )
    if feedback:
        user += (
            "\n\n# REVIEWER FEEDBACK ON YOUR PREVIOUS DRAFT (correct these):\n"
            + feedback
            + "\nGround every claim strictly in the RETRIEVED SOURCES and remove or hedge "
            "anything they do not support. Keep your Granted/Dismissed lean if the "
            "analogous cases still point one way, lowering confidence rather than "
            "retreating to 'Uncertain'; use 'Uncertain' only when the sources are "
            "genuinely too sparse or conflicting to lean either way. Return the JSON again."
        )

    model = get_settings().reasoning_model
    for attempt in range(2):
        try:
            raw = complete(
                model=model,
                system=system,
                user=user if attempt == 0 else user + "\n\nReturn VALID JSON ONLY.",
                temperature=0.0,
                json_mode=True,
                max_tokens=2400,
                reasoning_effort="low",
                seed=get_settings().llm_seed,
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


def predict_validated(
    reformulated_query: str,
    original_question: str,
    result: RetrievalResult,
    precedent: dict | None = None,
    classifier: dict | None = None,
) -> tuple[dict, dict]:
    prediction = predict(reformulated_query, original_question, result)

    if prediction.get("likely_outcome") == "Uncertain" and prediction.get("confidence") == "low":
        return prediction, validator_mod.public_view(validator_mod._pass(ok=True))

    context = _format_context(result)

    def _run_review(pred: dict):
        return validator_mod.review(
            question=original_question,
            context_block=context,
            draft=_render_draft(pred),
            result=result,
            cited_cases=pred.get("cited_cases", []),
            llm_outcome=pred.get("likely_outcome"),
            precedent=precedent,
            classifier=classifier,
        )

    crit = _run_review(prediction)
    validation = validator_mod.public_view(crit)

    if crit["verdict"] == "revise" and crit.get("feedback"):
        revised = predict(
            reformulated_query, original_question, result, feedback=crit["feedback"]
        )
        if revised.get("reasoning") != _FALLBACK_REASONING:
            prediction = revised
            validation["revised"] = True
            crit = _run_review(prediction)
            validation["confidence_ceiling"] = crit.get("max_confidence")

    ceiling = crit.get("max_confidence")
    if ceiling and prediction.get("confidence") in _VALID_CONFIDENCE:
        capped = validator_mod._cap_confidence(prediction["confidence"], ceiling)
        if capped != prediction["confidence"]:
            prediction["confidence"] = capped
            validation["confidence_capped_to"] = capped
    return prediction, validation
