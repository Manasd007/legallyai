from __future__ import annotations

import re
from dataclasses import dataclass, field

from server.config import get_settings

_SECTION_RE = re.compile(r"\b(?:Section|Article|Order)\s+\d{1,4}\s?[A-D]?\b(?:\s+(?:of\s+)?[A-Z][\w .]{2,40}Act)?", re.IGNORECASE)
_ACT_RE = re.compile(r"\b[A-Z][A-Za-z ]{2,40}\bAct\b|\bIPC\b|\bCrPC\b|\bCPC\b|\bRERA\b|\bPOCSO\b|\bNDPS\b|\bUAPA\b|\bPMLA\b|\bSARFAESI\b")
_AMOUNT_RE = re.compile(r"(?:₹|rs\.?|rupees?)\s?[\d,]+(?:\s?(?:lakh|lakhs|crore|crores|thousand|hazaar))?", re.IGNORECASE)


def _pretty_case(case: dict) -> str:
    name = str(case.get("case_name", "")).strip()
    citation = str(case.get("citation", "")).strip()
    if name:
        name = re.sub(r"\s+", " ", name).title()
        name = re.sub(r"\bVersus\b", "v.", name)
        if len(name) > 60:
            name = name[:57].rstrip() + "…"
    if name and citation:
        return f"{name} — {citation}"
    return name or citation


@dataclass
class ToolCallRecord:
    query: str
    n_cases: int
    weak: bool
    top_citations: list[str] = field(default_factory=list)


@dataclass
class DialogState:
    session_id: str
    topic: str = ""
    statutes: list[str] = field(default_factory=list)
    acts: list[str] = field(default_factory=list)
    amounts: list[str] = field(default_factory=list)
    retrievals: list[ToolCallRecord] = field(default_factory=list)
    undelivered_tail: str = ""
    turn_count: int = 0
    language_name: str = ""

    def note_user_turn(self, text: str) -> None:
        self.turn_count += 1
        self._extract_entities(text)

    def note_agent_turn(self, text: str) -> None:
        self._extract_entities(text)

    def note_tool_call(self, query: str, result: dict) -> None:
        self.topic = query
        cases = result.get("cases", []) if result.get("ok") else []
        self.retrievals.append(
            ToolCallRecord(
                query=query,
                n_cases=len(cases),
                weak=bool(result.get("weak_retrieval")),
                top_citations=[_pretty_case(c) for c in cases[:3]],
            )
        )

    def note_interruption(self, full_text: str, delivered_chars: int) -> None:
        tail = full_text[delivered_chars:].strip()
        self.undelivered_tail = tail[:400]

    def clear_undelivered(self) -> None:
        self.undelivered_tail = ""

    def _extract_entities(self, text: str) -> None:
        def _merge(target: list[str], found: list[str], cap: int = 6) -> None:
            for item in found:
                item = item.strip()
                if item and item.lower() not in (t.lower() for t in target):
                    target.append(item)
            del target[:-cap]

        _merge(self.statutes, _SECTION_RE.findall(text))
        _merge(self.acts, _ACT_RE.findall(text))
        _merge(self.amounts, _AMOUNT_RE.findall(text))

    def render(self) -> str:
        lines = ["[CONVERSATION STATE]"]
        if self.language_name:
            lines.append(
                f"[LANGUAGE] The caller is speaking {self.language_name}. "
                "Reply in that language."
            )
        if self.topic:
            lines.append(f"current_topic: {self.topic}")
        if self.statutes:
            lines.append(f"statutes_mentioned: {', '.join(self.statutes)}")
        if self.acts:
            lines.append(f"acts_mentioned: {', '.join(self.acts)}")
        if self.amounts:
            lines.append(f"amounts_mentioned: {', '.join(self.amounts)}")
        if self.retrievals:
            last = self.retrievals[-1]
            lines.append(
                f"last_search: \"{last.query}\" → {last.n_cases} cases"
                + (" (WEAK retrieval — must hedge)" if last.weak else "")
                + (f"; top: {'; '.join(c for c in last.top_citations if c)}" if last.top_citations else "")
            )
        if self.undelivered_tail:
            lines.append(
                "interrupted_last_answer: the user did NOT hear this part, do not "
                f"assume they know it: \"{self.undelivered_tail}\""
            )
        return "\n".join(lines) if len(lines) > 1 else ""


def trim_history(messages: list[dict]) -> list[dict]:
    limit = get_settings().max_history_messages
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    return system + rest[-limit:]
