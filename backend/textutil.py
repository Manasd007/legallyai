"""Small text helpers shared across modules."""
from __future__ import annotations

import re

# SCR-reporter PDFs carry margin letters ("A B C D E F G H", often one per line)
# and running page headers ("896 SUPREME COURT REPORTS"). Noise in a quoted excerpt.
_MARGIN_LETTERS = re.compile(r"(?:\b[A-Z]\b\s+){2,}")  # whitespace incl. newlines
_PAGE_HEADER = re.compile(r"\b\d{1,4}\s*SUPREME COURT REPORTS\b", re.IGNORECASE)
_MULTISPACE = re.compile(r"[ \t]{2,}")
_PARA_SPLIT = re.compile(r"\n\s*\n")


def clean_excerpt(text: str) -> str:
    """Strip common PDF-extraction noise from a judgment passage for display.

    Removes margin letters (incl. one-per-line) and running page headers, joins
    PDF line-wraps within a paragraph, and keeps paragraph breaks. Leaves the
    substantive text and inline citations untouched.
    """
    t = text or ""
    t = _MARGIN_LETTERS.sub(" ", t)
    t = _PAGE_HEADER.sub(" ", t)
    # Join hard line-wraps inside each paragraph; preserve blank-line paragraph breaks.
    paras = [_MULTISPACE.sub(" ", p.replace("\n", " ")).strip() for p in _PARA_SPLIT.split(t)]
    return "\n\n".join(p for p in paras if p).strip()
