"""Adaptive endpointing for Hinglish speech (context doc §4.1).

Hinglish speakers routinely pause mid-sentence while reaching for an English
legal word ("makaan malik ne mera deposit... uh... security deposit nahi diya").
A fixed silence threshold either cuts them off or adds dead air. This module
provides both endpointing modes the pipeline can run:

  * "adaptive" (default): Pipecat's SpeechTimeoutUserTurnStopStrategy with the
    patience EXTENDED whenever the transcript-so-far looks syntactically
    unfinished (trailing conjunction/postposition/filler, dangling "Section",
    trailing number...). Deterministic, zero extra inference cost, tunable
    against Hinglish recordings.
  * "smart_turn": Pipecat's local Smart Turn v3 model (semantic end-of-turn
    classification on the audio itself). Stronger on English; its Hinglish
    behavior is unvalidated, so it is opt-in until the §6.3 fixture set says
    otherwise.

Both are driven by Silero VAD upstream (wired in LLMUserAggregatorParams).
"""
from __future__ import annotations

import re

from pipecat.frames.frames import Frame, InterimTranscriptionFrame
from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from server.config import get_settings

# Words that, when FINAL in the utterance so far, signal the sentence is not
# done. Hindi postpositions/conjunctions (romanized), English connectives, and
# hesitation fillers. Deliberately conservative: a false "incomplete" costs a
# few hundred ms of patience; a false "complete" cuts the user off.
_CONTINUATION_TAIL = {
    # Hindi postpositions / particles — a sentence never ends on these
    "ka", "ke", "ki", "ko", "se", "mein", "me", "pe", "par", "tak", "wala", "wale", "wali",
    # Conjunctions
    "aur", "lekin", "magar", "kyunki", "agar", "jab", "phir", "toh", "to",
    "and", "but", "or", "so", "because", "if", "when", "then", "that",
    # Fillers / hesitation
    "uh", "um", "umm", "hmm", "matlab", "yaani", "like", "basically", "actually",
    # Dangling legal-reference starts
    "section", "dhara", "dafa", "article", "act", "under",
}

_TRAILING_NUMBER_RE = re.compile(r"\b\d{1,4}$")
_TRAILING_COMMA_RE = re.compile(r"[,…]\s*$")
# Spoken digits: "section one thirty <pause> eight" — a number word at the end
# of a section reference means the number itself may be unfinished.
_NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred",
}
_REFERENCE_WORDS = ("section", "dhara", "dafa", "article")


def looks_incomplete(text: str) -> bool:
    """Heuristic: does this partial utterance look like the user isn't done?"""
    text = text.strip().lower()
    if not text:
        return False
    if _TRAILING_COMMA_RE.search(text):
        return True
    # "section 138..." / "section one thirty..." — a trailing number (digit or
    # spoken) usually continues ("...ke under", "...eight"), but only when a
    # legal reference word precedes it.
    last_word = re.split(r"[\s,]+", text)[-1].strip(".!?")
    if any(w in text for w in _REFERENCE_WORDS) and (
        _TRAILING_NUMBER_RE.search(text) or last_word in _NUMBER_WORDS
    ):
        return True
    return last_word in _CONTINUATION_TAIL


class HinglishAdaptiveStopStrategy(SpeechTimeoutUserTurnStopStrategy):
    """Speech-timeout stop strategy with Hinglish-aware patience.

    When VAD reports silence, the parent starts a `user_speech_timeout` timer.
    Before that timer starts we look at everything transcribed so far this turn
    (final segments + the latest interim) and, if it looks unfinished, extend
    the timeout by `extra_patience` for this pause only.
    """

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
        # Track interims ourselves: the parent only accumulates FINAL segments,
        # but the freshest signal during a mid-sentence pause is the interim.
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
    """Turn strategies for the user aggregator. Start strategies stay at
    Pipecat defaults (VAD + transcription); only the stop side differs."""
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
