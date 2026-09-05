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
        self._seen: set[int] = set()
        self._t_vad_stop: float | None = None
        self._t_turn_stop: float | None = None
        self._tool_started: dict[str, float] = {}
        self._bot_started_this_turn = False

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if frame.id in self._seen:
            return
        self._seen.add(frame.id)
        if len(self._seen) > 8192:
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
            if "stt" in name and rec.stt_final_ms < 0:
                rec.stt_final_ms = ms
            elif "llm" in name and rec.llm_first_ms < 0:
                rec.llm_first_ms = ms
            elif "tts" in name and rec.tts_first_ms < 0:
                rec.tts_first_ms = ms
