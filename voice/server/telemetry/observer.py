"""Pipeline observer that turns frame traffic into per-stage latency numbers
(context doc §3: every turn logs per-stage timings from day one).

An observer sees every frame pushed anywhere in the pipeline without sitting in
the data path, so instrumentation adds nothing to the latency it measures.

Stage timing model per turn:

    VADUserStoppedSpeaking ─┐
                            ├─ endpoint_ms (silence → turn-over decision)
    UserStoppedSpeaking ────┘
    FunctionCallInProgress → FunctionCallResult   = tool_ms (wall clock)
    BotStartedSpeaking (output transport)         → e2e_ms since VAD stop
    MetricsFrame TTFB entries                     → llm_first_ms / tts_first_ms
"""
from __future__ import annotations

import logging
import time

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    FunctionCallInProgressFrame,
    FunctionCallResultFrame,
    MetricsFrame,
    UserStoppedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.metrics.metrics import TTFBMetricsData
from pipecat.observers.base_observer import BaseObserver, FramePushed

from server.pipeline.session import SessionHub

log = logging.getLogger("legallyai.voice.observer")


class TurnTelemetryObserver(BaseObserver):
    def __init__(self, hub: SessionHub, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hub = hub
        self._seen: set[int] = set()  # frame ids, since frames pass many processors
        self._t_vad_stop: float | None = None
        self._t_turn_stop: float | None = None
        self._tool_started: dict[str, float] = {}  # tool_call_id → t0
        self._bot_started_this_turn = False

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if frame.id in self._seen:
            return
        self._seen.add(frame.id)
        if len(self._seen) > 8192:  # bounded memory over long calls
            self._seen.clear()
        now = time.perf_counter()
        rec = self._hub.record

        if isinstance(frame, VADUserStoppedSpeakingFrame):
            self._t_vad_stop = now
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._t_turn_stop = now
            self._bot_started_this_turn = False
            if rec and self._t_vad_stop is not None:
                rec.endpoint_ms = int((now - self._t_vad_stop) * 1000)
        elif isinstance(frame, FunctionCallInProgressFrame):
            self._tool_started[frame.tool_call_id] = now
        elif isinstance(frame, FunctionCallResultFrame):
            t0 = self._tool_started.pop(frame.tool_call_id, None)
            if rec and t0 is not None:
                rec.tool_ms += int((now - t0) * 1000)
        elif isinstance(frame, BotStartedSpeakingFrame):
            if rec and not self._bot_started_this_turn:
                self._bot_started_this_turn = True
                ref = self._t_vad_stop or self._t_turn_stop
                if ref is not None:
                    rec.e2e_ms = int((now - ref) * 1000)
        elif isinstance(frame, MetricsFrame):
            self._absorb_metrics(frame)

    def _absorb_metrics(self, frame: MetricsFrame) -> None:
        rec = self._hub.record
        if rec is None:
            return
        for item in frame.data:
            if not isinstance(item, TTFBMetricsData) or not item.value:
                continue
            ms = int(item.value * 1000)
            name = (item.processor or "").lower()
            # First TTFB of the turn wins; later ones belong to post-tool re-runs.
            # NOTE: "stt" must be checked before "tts" — "...sttservice" also
            # contains the substring "tts".
            if "stt" in name and rec.stt_final_ms < 0:
                rec.stt_final_ms = ms
            elif "llm" in name and rec.llm_first_ms < 0:
                rec.llm_first_ms = ms
            elif "tts" in name and rec.tts_first_ms < 0:
                rec.tts_first_ms = ms
