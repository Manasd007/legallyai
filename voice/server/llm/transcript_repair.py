from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("legallyai.voice.repair")

VOCAB_PATH = Path(__file__).resolve().parent.parent.parent / "vocab" / "legal_terms.txt"

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_NUM_WORD = r"(?:%s)" % "|".join(
    sorted(["hundred", "and", *_UNITS, *_TENS], key=len, reverse=True)
)
_LABELS = {
    "section": "Section", "dhara": "Section", "dafa": "Section",
    "article": "Article", "anuchhed": "Article", "anuched": "Article",
}
_LABEL_ALT = "|".join(_LABELS)
_REF_WORDS_RE = re.compile(
    r"\b(%s)\s+((?:%s)(?:\s+(?:%s)){0,4})(\s*)" % (_LABEL_ALT, _NUM_WORD, _NUM_WORD),
    re.IGNORECASE,
)
_REF_DIGITS_RE = re.compile(
    r"\b(%s)\s+(\d{1,4})(?:\s?([a-dA-D]))?\b" % _LABEL_ALT, re.IGNORECASE
)


def _words_to_number(words: str) -> int | None:
    tokens = [t for t in re.split(r"\s+", words.strip().lower()) if t and t != "and"]
    if not tokens:
        return None
    if all(t in _UNITS and _UNITS[t] < 10 for t in tokens) and len(tokens) > 1:
        return int("".join(str(_UNITS[t]) for t in tokens))
    parts: list[int] = []
    current = 0
    for t in tokens:
        if t == "hundred":
            current = (current or 1) * 100
        elif t in _TENS:
            if current and current < 20:
                parts.append(current)
                current = 0
            current += _TENS[t]
        elif t in _UNITS:
            if current and current % 10 == 0:
                current += _UNITS[t]
            elif current:
                parts.append(current)
                current = _UNITS[t]
            else:
                current = _UNITS[t]
        else:
            return None
    parts.append(current)
    if not parts:
        return None
    return int("".join(str(p) for p in parts))


@lru_cache(maxsize=1)
def _substitutions() -> list[tuple[re.Pattern, str]]:
    table: list[tuple[str, str]] = [
        (r"\bn\.?\s?i\.?\s+act\b", "NI Act"),
        (r"\bnegotiable instrument(s)? act\b", "Negotiable Instruments Act"),
        (r"\bcheck bounce\b", "cheque bounce"),
        (r"\bcheck bounse\b", "cheque bounce"),
        (r"\bi\.?\s?p\.?\s?c\b", "IPC"),
        (r"\bindian penal code\b", "Indian Penal Code"),
        (r"\bc\.?\s?r\.?\s?p\.?\s?c\b", "CrPC"),
        (r"\bc\.?\s?p\.?\s?c\b(?!\w)", "CPC"),
        (r"\bpocso\b", "POCSO Act"),
        (r"\bpokso\b", "POCSO Act"),
        (r"\bndps\b", "NDPS Act"),
        (r"\barticle (\d{1,3})\b", r"Article \1"),
        (r"\bfir\b", "FIR"),
        (r"\banticipatory bell\b", "anticipatory bail"),
        (r"\bbell application\b", "bail application"),
        (r"\bwrit petition\b", "writ petition"),
        (r"\bhabeas? corpus\b", "habeas corpus"),
        (r"\bmoter vehicles? act\b", "Motor Vehicles Act"),
        (r"\bhindu marriage act\b", "Hindu Marriage Act"),
        (r"\bdomestic violence act\b", "Domestic Violence Act"),
        (r"\bdowry prohibition act\b", "Dowry Prohibition Act"),
        (r"\bconsumer protection act\b", "Consumer Protection Act"),
        (r"\brent control act\b", "Rent Control Act"),
        (r"\bspecific relief act\b", "Specific Relief Act"),
        (r"\blimitation act\b", "Limitation Act"),
        (r"\barbitration act\b", "Arbitration Act"),
    ]
    if VOCAB_PATH.exists():
        for line in VOCAB_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=>" not in line:
                continue
            wrong, right = (part.strip() for part in line.split("=>", 1))
            if wrong and right:
                table.append((r"\b" + re.escape(wrong) + r"\b", right))
    return [(re.compile(pat, re.IGNORECASE), rep) for pat, rep in table]


def repair(text: str) -> str:
    if not text:
        return text
    original = text

    def _ref(m: re.Match) -> str:
        label = _LABELS[m.group(1).lower()]
        n = _words_to_number(m.group(2))
        return f"{label} {n}{m.group(3)}" if n is not None else m.group(0)

    text = _REF_WORDS_RE.sub(_ref, text)
    text = _REF_DIGITS_RE.sub(
        lambda m: f"{_LABELS[m.group(1).lower()]} {m.group(2)}"
        + (m.group(3).upper() if m.group(3) else ""),
        text,
    )

    for pattern, replacement in _substitutions():
        text = pattern.sub(replacement, text)

    if text != original:
        log.info("repaired transcript: %r -> %r", original, text)
    return text
