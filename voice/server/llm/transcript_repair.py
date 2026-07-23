"""Transcript repair: normalize obvious STT mis-transcriptions of Indian legal
terms BEFORE they reach the LLM and retrieval (context doc §4.3c).

A misheard legal term is dangerous — "section one thirty eight" retrieving
nothing (or the wrong section) produces a confidently wrong answer. This is a
deterministic, zero-latency rule pass, deliberately NOT an LLM call: it runs on
every final transcript and must add ~0ms to the turn.

Two layers:
  1. Spoken-number normalization for section references
     ("section one thirty eight" / "section one three eight" → "Section 138").
  2. A phrase-substitution table for commonly garbled act names and terms,
     seeded here and extendable via vocab/legal_terms.txt (lines of the form
     `wrong phrase => Right Phrase`).
"""
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
# Longest-first: regex alternation is first-match-wins, so listing "four" before
# "fourteen" makes "fourteen" match as "four" and strand a literal "teen"
# ("anuchhed fourteen" → "Article 4teen").
_NUM_WORD = r"(?:%s)" % "|".join(
    sorted(["hundred", "and", *_UNITS, *_TENS], key=len, reverse=True)
)
# Spoken references normalise to a canonical label. "dhara"/"dafa" are Hindi for
# section; "anuchhed" is Hindi for article. Articles matter as much as sections —
# "article twenty one" left as words retrieves nothing for Article 21.
_LABELS = {
    "section": "Section", "dhara": "Section", "dafa": "Section",
    "article": "Article", "anuchhed": "Article", "anuched": "Article",
}
_LABEL_ALT = "|".join(_LABELS)
# The trailing `\s*` is INSIDE the repeat group but must not be swallowed: it
# used to be consumed into the match and dropped by the replacement, producing
# "Section 138ka case" — glued words that then went on to retrieval as-is.
# Capturing it separately lets the replacement put it back.
_REF_WORDS_RE = re.compile(
    r"\b(%s)\s+((?:%s)(?:\s+(?:%s)){0,4})(\s*)" % (_LABEL_ALT, _NUM_WORD, _NUM_WORD),
    re.IGNORECASE,
)
# The sub-clause letter ("138A") is captured separately rather than as part of a
# `\d{1,4}\s?[a-dA-D]?` blob: that blob absorbed the following space, which the
# replacement then stripped, gluing the next word on ("Section 138notice").
_REF_DIGITS_RE = re.compile(
    r"\b(%s)\s+(\d{1,4})(?:\s?([a-dA-D]))?\b" % _LABEL_ALT, re.IGNORECASE
)


def _words_to_number(words: str) -> int | None:
    """Parse spoken section numbers, both digit-by-digit ("one three eight")
    and place-value ("one thirty eight", "four twenty", "three hundred two")."""
    tokens = [t for t in re.split(r"\s+", words.strip().lower()) if t and t != "and"]
    if not tokens:
        return None
    # Digit-by-digit reading: every token a unit < 10 → concatenate.
    if all(t in _UNITS and _UNITS[t] < 10 for t in tokens) and len(tokens) > 1:
        return int("".join(str(_UNITS[t]) for t in tokens))
    # Place-value reading with concatenation for section-style numbers:
    # "one thirty eight" → 1·100? No — spoken sections concatenate: 1|38 → 138.
    parts: list[int] = []
    current = 0
    for t in tokens:
        if t == "hundred":
            current = (current or 1) * 100
        elif t in _TENS:
            if current and current < 20:
                parts.append(current)  # "one thirty…" → flush the 1, start 30
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
    """Common mishearings, seeded + loaded from vocab/legal_terms.txt."""
    table: list[tuple[str, str]] = [
        # Act names STT often garbles in code-switched speech
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
    # vocab file lines: `wrong phrase => Right Phrase` (comments with #)
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
    """Normalize a final STT transcript. Deterministic and idempotent."""
    if not text:
        return text
    original = text

    # 1) Spoken section/article numbers → digits, preserving the trailing space.
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

    # 2) Phrase substitutions
    for pattern, replacement in _substitutions():
        text = pattern.sub(replacement, text)

    if text != original:
        log.info("repaired transcript: %r -> %r", original, text)
    return text
