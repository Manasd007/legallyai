from __future__ import annotations

import re

from pipecat.frames.frames import Frame, InterimTranscriptionFrame
from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from server.config import get_settings

_CONTINUATION_TAIL = {
    "ka", "ke", "ki", "ko", "se", "mein", "me", "pe", "par", "tak", "wala", "wale", "wali",
    "aur", "lekin", "magar", "kyunki", "agar", "jab", "phir", "toh", "to",
    "and", "but", "or", "so", "because", "if", "when", "then", "that",
    "uh", "um", "umm", "hmm", "matlab", "yaani", "like", "basically", "actually",
    "section", "dhara", "dafa", "article", "act", "under",
}

_TRAILING_NUMBER_RE = re.compile(r"\b\d{1,4}$")
_TRAILING_COMMA_RE = re.compile(r"[,…]\s*$")
_NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred",
}
_REFERENCE_WORDS = ("section", "dhara", "dafa", "article")


def looks_incomplete(text: str) -> bool:
    text = text.strip().lower()
    if not text:
        return False
    if _TRAILING_COMMA_RE.search(text):
        return True
    last_word = re.split(r"[\s,]+", text)[-1].strip(".!?")
    if any(w in text for w in _REFERENCE_WORDS) and (
        _TRAILING_NUMBER_RE.search(text) or last_word in _NUMBER_WORDS
    ):
        return True
    return last_word in _CONTINUATION_TAIL


class HinglishAdaptiveStopStrategy(SpeechTimeoutUserTurnStopStrategy):

    def __init__(
        self,
        *,
        user_speech_timeout: float,
        extra_patience: float,
        **kwargs,
    ) -> None:
        super().__init__(user_speech_timeout=user_speech_timeout, **kwargs)
        self._base_timeout = user_speech_timeout
        self._extra_patience = extra_patience
        self._interim_text = ""

    async def process_frame(self, frame: Frame):
        if isinstance(frame, InterimTranscriptionFrame):
            self._interim_text = frame.text or ""
        return await super().process_frame(frame)

    async def reset(self):
        await super().reset()
        self._interim_text = ""

    async def _handle_vad_user_stopped_speaking(self, frame):
        turn_text = f"{self._text} {self._interim_text}".strip()
        if looks_incomplete(turn_text):
            self._user_speech_timeout = self._base_timeout + self._extra_patience
        else:
            self._user_speech_timeout = self._base_timeout
        await super()._handle_vad_user_stopped_speaking(frame)


def build_turn_strategies(mode: str = "adaptive") -> UserTurnStrategies:
    s = get_settings()
    if mode == "smart_turn":
        from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
        from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy

        stop = [TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())]
    else:
        stop = [
            HinglishAdaptiveStopStrategy(
                user_speech_timeout=s.vad_stop_secs,
                extra_patience=s.endpoint_extra_patience_s,
            )
        ]
    return UserTurnStrategies(stop=stop)
