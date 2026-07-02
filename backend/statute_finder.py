"""Statute & Section Finder.

Given a situation, identify the Indian Acts/sections most likely to govern it and
link them to retrieved judgments that apply them. Statute names are public legal
facts; the prompt forbids fabricating section numbers and prefers provisions that
actually appear in the retrieved cases.
"""
from __future__ import annotations

import json
import logging

from config import get_settings, load_prompt
from llm import complete
import legal_qa as legal_qa_mod
import reformulate as reformulate_mod
import retrieval as retrieval_mod

log = logging.getLogger("legally.statutes")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t[3:]
        t = t.removeprefix("json").strip().removesuffix("```").strip()
    return t


def _normalize(data: dict) -> dict:
    statutes = []
    for s in data.get("statutes") or []:
        if not isinstance(s, dict):
            continue
        statutes.append({
            "act": str(s.get("act", "")).strip(),
            "section": str(s.get("section", "")).strip(),
            "what_it_governs": str(s.get("what_it_governs", "")).strip(),
            "relevance": str(s.get("relevance", "")).strip(),
        })
    return {
        "situation_summary": str(data.get("situation_summary", "")),
        "statutes": [s for s in statutes if s["act"]],
        "note": str(data.get("note", "")),
    }


def find(question: str) -> dict:
    s = get_settings()
    reformulated = reformulate_mod.reformulate(question)
    result = retrieval_mod.retrieve(reformulated, question)  # may raise FileNotFoundError

    cases = legal_qa_mod._dedupe_cases(result)
    context = legal_qa_mod._format_context(result)
    weak = result.max_similarity < s.similarity_threshold

    system = load_prompt("statute_finder_system_v1.txt")
    user = (
        f"USER SITUATION:\n{question}\n\n"
        "RETRIEVED CASES (prefer statutes/sections that appear here):\n"
        f"{context}\n\n"
        "Return the JSON now."
    )

    out = {"situation_summary": "", "statutes": [], "note": ""}
    for attempt in range(2):
        try:
            raw = complete(
                model=s.reasoning_model,
                system=system,
                user=user if attempt == 0 else user + "\n\nReturn VALID JSON ONLY.",
                temperature=0.2,
                json_mode=True,
                max_tokens=1200,
            )
            out = _normalize(json.loads(_strip_fences(raw)))
            break
        except json.JSONDecodeError as e:
            log.warning("Statute finder JSON parse failed (attempt %d): %s", attempt + 1, e)
            continue
        except Exception as e:  # noqa: BLE001
            log.error("Statute finder call failed: %s", e)
            break

    return {**out, "related_cases": cases, "weak_retrieval": weak}
