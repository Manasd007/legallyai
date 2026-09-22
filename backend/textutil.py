from __future__ import annotations

import re

_MARGIN_LETTERS = re.compile(r"(?:\b[A-Z]\b\s+){2,}")
_PAGE_HEADER = re.compile(r"\b\d{1,4}\s*SUPREME COURT REPORTS\b", re.IGNORECASE)
_MULTISPACE = re.compile(r"[ \t]{2,}")
_PARA_SPLIT = re.compile(r"\n\s*\n")


def clean_excerpt(text: str) -> str:
    t = text or ""
    t = _MARGIN_LETTERS.sub(" ", t)
    t = _PAGE_HEADER.sub(" ", t)
    paras = [_MULTISPACE.sub(" ", p.replace("\n", " ")).strip() for p in _PARA_SPLIT.split(t)]
    return "\n\n".join(p for p in paras if p).strip()


_SMALLTALK_PHRASES: frozenset[str] = frozenset({
    "hi", "hii", "hiii", "hey", "heya", "hello", "helo", "hellooo", "yo",
    "hola", "namaste", "namaskar", "hi there", "hello there", "hey there",
    "good morning", "good afternoon", "good evening", "good night", "gm", "ge",
    "morning", "sup", "wassup", "whats up", "what's up", "how are you",
    "how are you doing", "how's it going", "hows it going",
    "thanks", "thank you", "thank u", "thanks a lot", "thanks so much",
    "thank you so much", "thx", "tysm", "ty", "cheers", "much appreciated",
    "ok", "okay", "okey", "k", "kk", "cool", "nice", "great", "awesome",
    "got it", "understood", "no problem", "np",
    "bye", "goodbye", "good bye", "see you", "see ya", "cya", "later",
    "who are you", "what are you", "what can you do", "what do you do",
    "what is this", "who r u", "help", "test", "testing", "hi bot",
})

_SMALLTALK_STRIP = re.compile(r"[\s!.?,'\"~*_\-)(]+$")
_LEADING_STRIP = re.compile(r"^[\s!.?,'\"~*_\-)(]+")
_HAS_LETTER = re.compile(r"[a-zA-Zऀ-ॿ]")


_MOJIBAKE = {
    "â€™": "'", "â€˜": "'",
    "â€œ": '"', "â€": '"', "â€�": '"',
    "â€”": ", ", "â€“": "-",
    "â€¯": " ", "â€¦": "...",
    "Â ": " ", "Â": "",
}
_PUNCT_MAP = {
    0x2019: "'", 0x2018: "'", 0x201C: '"', 0x201D: '"', 0xFFFD: "",
    0x2014: ", ", 0x2013: "-", 0x2011: "-", 0x2026: "...",
    0x00A0: " ", 0x202F: " ", 0x2009: " ", 0x2007: " ", 0x200B: "",
}


def normalize_text(text: str) -> str:
    text = text or ""
    for k, v in _MOJIBAKE.items():
        if k in text:
            text = text.replace(k, v)
    return text.translate(_PUNCT_MAP)


_QUERY_TRAIL = re.compile(r"[\s!?.,;:'\"~*_)(\-]+$")
_QUERY_LEAD = re.compile(r"^[\s!?.,;:'\"~*_)(\-]+")
_QUERY_WS = re.compile(r"\s+")


def normalize_query(text: str) -> str:
    """Canonical form of a user question, used as the cache/retrieval key.

    Two questions that differ only in casing, surrounding punctuation, smart
    quotes, or internal whitespace collapse to the same string, so trivial
    rewordings ("Can I appeal?" / "can i appeal") hit the same cached answer
    and drive the same retrieval instead of re-rolling the LLM pipeline.
    """
    t = normalize_text(text or "").lower()
    t = _QUERY_WS.sub(" ", t).strip()
    t = _QUERY_LEAD.sub("", _QUERY_TRAIL.sub("", t))
    return t


def is_smalltalk(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    if not _HAS_LETTER.search(t):
        return True
    t = _LEADING_STRIP.sub("", _SMALLTALK_STRIP.sub("", t))
    t = re.sub(r"\s+", " ", t)
    return t in _SMALLTALK_PHRASES
