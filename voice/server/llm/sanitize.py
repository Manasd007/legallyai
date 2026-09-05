from __future__ import annotations

import re

_COMPLETE = re.compile(r"<function[^>]*>.*?</function>\"?", re.DOTALL | re.IGNORECASE)
_TOOL_CALL = re.compile(r"<tool_call>.*?</tool_call>", re.DOTALL | re.IGNORECASE)
_UNTERMINATED = re.compile(r"<function[^>]*>.*", re.DOTALL | re.IGNORECASE)
_STRAY_TAG = re.compile(r"</?function[^>]*>|</?tool_call>", re.IGNORECASE)
_LLAMA_SPECIAL = re.compile(r"<\|python_tag\|>.*|<\|eom_id\|>|<\|eot_id\|>", re.DOTALL)
_SPACES = re.compile(r"[ \t]{2,}")


def strip_tool_markup(text: str) -> str:
    for pattern in (_COMPLETE, _TOOL_CALL, _UNTERMINATED, _STRAY_TAG, _LLAMA_SPECIAL):
        text = pattern.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def strip_complete_markup(text: str) -> str:
    for pattern in (_COMPLETE, _TOOL_CALL, _LLAMA_SPECIAL):
        text = pattern.sub(" ", text)
    return text


_MARKUP_OPENERS = ("<function", "</function", "<tool_call", "</tool_call", "<|")


def markup_hold_index(buffer: str) -> int | None:
    i = buffer.find("<")
    while i != -1:
        tail = buffer[i:]
        for opener in _MARKUP_OPENERS:
            if tail.startswith(opener) or opener.startswith(tail):
                return i
        i = buffer.find("<", i + 1)
    return None
