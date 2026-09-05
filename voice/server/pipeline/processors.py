from __future__ import annotations

import logging

from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    Frame,
    InterimTranscriptionFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    TranscriptionFrame,
    TTSTextFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from server.llm.sanitize import markup_hold_index, strip_complete_markup, strip_tool_markup
from server.llm.transcript_repair import repair
from server.pipeline.session import SessionHub

log = logging.getLogger("legallyai.voice.processors")


class TranscriptRepairProcessor(FrameProcessor):
    def __init__(self, hub: SessionHub, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hub = hub

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text:
            frame.text = repair(frame.text)
            self._hub.note_detected_language(frame.language)
            self._hub.user_final(frame.text)
        elif isinstance(frame, InterimTranscriptionFrame) and frame.text:
            self._hub.user_partial(frame.text)
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._hub.user_turn_committed()
        await self.push_frame(frame, direction)


class FunctionCallMarkupFilter(FrameProcessor):

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._buffer = ""

    async def _emit(self, text: str, direction: FrameDirection) -> None:
        if text:
            await self.push_frame(LLMTextFrame(text), direction)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMTextFrame) and frame.text:
            self._buffer += frame.text
            self._buffer = strip_complete_markup(self._buffer)
            hold = markup_hold_index(self._buffer)
            if hold is None:
                await self._emit(self._buffer, direction)
                self._buffer = ""
            else:
                await self._emit(self._buffer[:hold], direction)
                self._buffer = self._buffer[hold:]
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            await self._emit(strip_tool_markup(self._buffer), direction)
            self._buffer = ""
        elif isinstance(frame, InterruptionFrame):
            self._buffer = ""

        await self.push_frame(frame, direction)


class GeneratedTextTracker(FrameProcessor):
    def __init__(self, hub: SessionHub, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hub = hub

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TTSTextFrame) and frame.text:
            sep = "" if frame.includes_inter_frame_spaces else " "
            self._hub.agent_text_generated(frame.text + sep if sep else frame.text)
        await self.push_frame(frame, direction)


class DeliveredTextTracker(FrameProcessor):
    def __init__(self, hub: SessionHub, **kwargs) -> None:
        super().__init__(**kwargs)
        self._hub = hub

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TTSTextFrame) and frame.text:
            sep = "" if frame.includes_inter_frame_spaces else " "
            self._hub.agent_text_delivered(frame.text + sep if sep else frame.text)
        elif isinstance(frame, InterruptionFrame):
            self._hub.agent_interrupted()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._hub.agent_finished()
        await self.push_frame(frame, direction)
