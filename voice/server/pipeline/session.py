"""Per-call session hub: the single place where transcript, dialog state and
turn telemetry meet.

Pipeline processors and the telemetry observer are deliberately thin — they
detect events and report them here. The hub owns the bookkeeping the context
doc calls the backbone: barge-in partial-delivery tracking (§4.2), structured
dialog state (§4.5), per-turn latency records (§3) and the transcript that
feeds the post-call summary.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from server.llm.dialog_state import DialogState
from server.llm.languages import DEFAULT_CODE, normalize, profile_for
from server.llm.sanitize import strip_tool_markup
from server.telemetry.events import bus
from server.telemetry.turns import TurnLog, TurnRecord

log = logging.getLogger("legallyai.voice.session")


class SessionHub:
    def __init__(self, session_id: str, turn_log: TurnLog) -> None:
        self.session_id = session_id
        self.state = DialogState(session_id=session_id)
        self.turn_log = turn_log
        self.transcript: list[dict] = []  # [{"role", "content"}] for the summary
        self.turn_index = 0
        self.record: TurnRecord | None = None  # the turn currently in flight
        # Bot-speech bookkeeping for the current agent turn
        self._generated_text = ""
        self._delivered_text = ""
        self._agent_turn_open = False
        # Set by the pipeline builder: refreshes the LLM context (state block +
        # history cap) right after a user turn commits, before the LLM runs.
        self.on_turn_committed: Callable[[], None] | None = None
        # Language of the call, from Deepgram's per-transcript detection. Drives
        # the TTS voice and the spoken fillers, both of which bypass the LLM.
        self.language: str = DEFAULT_CODE
        self._lang_candidate: str | None = None
        self._lang_detected = False  # has any final reported a language yet?
        # Set by the builder to retune TTS when the language changes.
        self.on_language_changed: Callable[[str], None] | None = None

    # ── Language ─────────────────────────────────────────────
    def note_detected_language(self, language: object) -> None:
        """Record the language Deepgram detected on a final transcript.

        The FIRST detection of the call applies at once: `language` starts at a
        default nobody chose, so making an English caller finish two turns of
        Hindi before it corrects is the very bug this exists to fix.

        Every later change needs the same language on two consecutive finals.
        Code-switched Hinglish makes per-utterance detection flip between `hi`
        and `en`, and swapping the TTS voice on each flip is far more jarring
        than reacting one turn late.
        """
        code = normalize(language)
        if code is None:
            return
        # Any recognised code counts as "the call's language is now known",
        # including one that matches the default — otherwise a caller who
        # happens to speak the default language would leave the first-detection
        # fast path armed, and one stray misdetection later would switch on it.
        first = not self._lang_detected
        self._lang_detected = True
        if code == self.language:
            self._lang_candidate = None
            return
        if not first and self._lang_candidate != code:
            self._lang_candidate = code
            return
        self.language = code
        self._lang_candidate = None
        self.state.language_name = profile_for(code).name
        log.info("session %s switched language to %s", self.session_id, code)
        if self.on_language_changed is not None:
            self.on_language_changed(code)

    # ── User side ────────────────────────────────────────────
    def user_partial(self, text: str) -> None:
        # While an utterance is in flight its partials belong to the SAME turn
        # as the finals already received — keying them to turn_index+1 after
        # the first final created stray duplicate bubbles in the UI (live-call
        # bug, 2026-07-20).
        turn = self.record.turn_index if self.record is not None else self.turn_index + 1
        bus.publish(self.session_id, "transcript.user.partial",
                    {"turn": turn, "text": text})

    def user_final(self, text: str) -> None:
        """A repaired final transcript segment arrived — the next turn is live."""
        if self.record is None:
            self.turn_index += 1
            self.record = TurnRecord(session_id=self.session_id, turn_index=self.turn_index)
        rec = self.record
        rec.user_text = (rec.user_text + " " + text).strip()
        bus.publish(self.session_id, "transcript.user.final",
                    {"turn": rec.turn_index, "text": rec.user_text})

    def user_turn_committed(self) -> None:
        """The endpointer declared the user turn over; state + transcript update."""
        if self.record and self.record.user_text:
            self.state.note_user_turn(self.record.user_text)
            self.transcript.append({"role": "user", "content": self.record.user_text})
        if self.on_turn_committed is not None:
            self.on_turn_committed()

    # ── Tool side ────────────────────────────────────────────
    def tool_called(self, query: str) -> None:
        if self.record:
            self.record.tool_called = True
            self.record.tool_query = query
        bus.publish(self.session_id, "status", {"text": "Searching case law…"})

    def tool_finished(self, query: str, result: dict, elapsed_ms: int) -> None:
        self.state.note_tool_call(query, result)
        if self.record:
            self.record.tool_ms = elapsed_ms
            self.record.weak_retrieval = bool(result.get("weak_retrieval"))
        # UI chrome, not speech — always English, and it must match the label the
        # client shows before the first tool call so the bar doesn't change
        # wording mid-conversation.
        bus.publish(self.session_id, "status", {"text": "Listening"})

    # ── Agent side ───────────────────────────────────────────
    def agent_text_generated(self, text: str) -> None:
        if not self._agent_turn_open:
            self._agent_turn_open = True
            self._generated_text = ""
            self._delivered_text = ""
        self._generated_text += text
        # Markup is filtered upstream before TTS; stripping again here keeps
        # the live transcript clean even for text that bypassed the filter
        # (e.g. TTSSpeakFrame acks would be clean anyway — defense in depth).
        bus.publish(self.session_id, "transcript.agent",
                    {"turn": self.turn_index, "text": strip_tool_markup(self._generated_text)})

    def agent_text_delivered(self, text: str) -> None:
        self._delivered_text += text

    def agent_interrupted(self) -> None:
        """Barge-in (§4.2): mark undelivered tail so the LLM never assumes the
        user heard the cut-off part. Delivered length is estimated from the
        text frames that made it through the output transport before the cut."""
        if not self._agent_turn_open:
            return
        delivered = len(self._delivered_text.strip())
        self.state.note_interruption(self._generated_text.strip(), delivered)
        if self.record:
            self.record.interrupted = True
            self.record.delivered_chars = delivered
        bus.publish(self.session_id, "agent.interrupted", {"turn": self.turn_index})
        self._close_agent_turn()

    def agent_finished(self) -> None:
        """Bot finished speaking normally — everything generated was heard."""
        if not self._agent_turn_open:
            return
        self.state.clear_undelivered()
        self._close_agent_turn()

    def _close_agent_turn(self) -> None:
        text = strip_tool_markup(self._generated_text)
        if text:
            self.state.note_agent_turn(text)
            self.transcript.append({"role": "assistant", "content": text})
        if self.record:
            self.record.agent_text = text
            if not self.record.interrupted:
                self.record.delivered_chars = len(text)
            self.turn_log.append(self.record)
            bus.publish(
                self.session_id, "latency.turn",
                {"turn": self.turn_index, "stages": {
                    "endpoint_ms": self.record.endpoint_ms,
                    "stt_final_ms": self.record.stt_final_ms,
                    "llm_first_ms": self.record.llm_first_ms,
                    "tool_ms": self.record.tool_ms,
                    "tts_first_ms": self.record.tts_first_ms,
                    "e2e_ms": self.record.e2e_ms,
                }},
            )
        self.record = None
        self._agent_turn_open = False
        self._generated_text = ""
        self._delivered_text = ""
