"""Strips tool-call markup that small Llama models sometimes emit as plain
text instead of using the function-calling interface, e.g.:

    <function=legal_search>{"query": "tenant rights"}"</function>

Anything like that must never reach TTS (it gets spoken aloud) or the
transcript/summary. Two layers use this module:

  * FunctionCallMarkupFilter (pipeline) — streaming-safe removal before TTS.
  * SessionHub / summary — final-text defense in depth.
"""
from __future__ import annotations

import re

# Complete blocks first, then unterminated tails, then stray tags/specials.
_COMPLETE = re.compile(r"<function[^>]*>.*?</function>\"?", re.DOTALL | re.IGNORECASE)
_TOOL_CALL = re.compile(r"<tool_call>.*?</tool_call>", re.DOTALL | re.IGNORECASE)
_UNTERMINATED = re.compile(r"<function[^>]*>.*", re.DOTALL | re.IGNORECASE)
_STRAY_TAG = re.compile(r"</?function[^>]*>|</?tool_call>", re.IGNORECASE)
_LLAMA_SPECIAL = re.compile(r"<\|python_tag\|>.*|<\|eom_id\|>|<\|eot_id\|>", re.DOTALL)
_SPACES = re.compile(r"[ \t]{2,}")


def strip_tool_markup(text: str) -> str:
    """Remove every form of leaked tool-call syntax from a COMPLETE text.

    Not streaming-safe (the unterminated-tail rule would eat legitimate text
    that merely hasn't finished arriving) — for streaming use the pipeline
    filter, which only applies the tail rule at flush time.
    """
    for pattern in (_COMPLETE, _TOOL_CALL, _UNTERMINATED, _STRAY_TAG, _LLAMA_SPECIAL):
        text = pattern.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def strip_complete_markup(text: str) -> str:
    """Remove only unambiguous, fully-delimited markup — safe mid-stream."""
    for pattern in (_COMPLETE, _TOOL_CALL, _LLAMA_SPECIAL):
        text = pattern.sub(" ", text)
    return text


# Openers we must never let through mid-stream. If the tail of the buffer is a
# prefix of one of these (or starts with one whose closer hasn't arrived yet),
# the filter withholds it until it can decide.
_MARKUP_OPENERS = ("<function", "</function", "<tool_call", "</tool_call", "<|")


def markup_hold_index(buffer: str) -> int | None:
    """Index from which `buffer` must be withheld, or None to emit all.

    Scans for the earliest '<' whose following text is (a prefix of) a markup
    opener. Ordinary '<' followed by something else — "5 < 7" — is let through.
    """
    i = buffer.find("<")
    while i != -1:
        tail = buffer[i:]
        for opener in _MARKUP_OPENERS:
            if tail.startswith(opener) or opener.startswith(tail):
                return i
        i = buffer.find("<", i + 1)
    return None
