from __future__ import annotations

from collections.abc import AsyncGenerator

import av
import edge_tts
from pipecat.frames.frames import ErrorFrame, Frame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService

EDGE_NATIVE_RATE = 24000


class EdgeTTSService(TTSService):

    def __init__(
        self,
        *,
        voice: str = "hi-IN-SwaraNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        sample_rate: int | None = EDGE_NATIVE_RATE,
        **kwargs,
    ) -> None:
        super().__init__(
            sample_rate=sample_rate,
            pause_frame_processing=True,
            push_start_frame=True,
            push_stop_frames=True,
            settings=TTSSettings(model="edge-neural", voice=voice),
            **kwargs,
        )
        self._voice = voice
        self._rate = rate
        self._pitch = pitch

    def can_generate_metrics(self) -> bool:
        return True

    def set_voice_name(self, voice: str) -> None:
        self._voice = voice

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        communicate = edge_tts.Communicate(
            text, voice=self._voice, rate=self._rate, pitch=self._pitch
        )
        decoder = av.CodecContext.create("mp3", "r")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=self.sample_rate)
        measuring_ttfb = True
        try:
            async for chunk in communicate.stream():
                if chunk["type"] != "audio" or not chunk["data"]:
                    continue
                if measuring_ttfb:
                    await self.stop_ttfb_metrics()
                    measuring_ttfb = False
                for packet in decoder.parse(chunk["data"]):
                    for decoded in decoder.decode(packet):
                        for out in resampler.resample(decoded):
                            pcm = out.to_ndarray().tobytes()
                            if pcm:
                                yield TTSAudioRawFrame(
                                    pcm, self.sample_rate, 1, context_id=context_id
                                )
            for decoded in decoder.decode(None):
                for out in resampler.resample(decoded):
                    pcm = out.to_ndarray().tobytes()
                    if pcm:
                        yield TTSAudioRawFrame(pcm, self.sample_rate, 1, context_id=context_id)
            for out in resampler.resample(None):
                pcm = out.to_ndarray().tobytes()
                if pcm:
                    yield TTSAudioRawFrame(pcm, self.sample_rate, 1, context_id=context_id)
        except Exception as e:  # noqa: BLE001 — a TTS failure must not kill the call
            yield ErrorFrame(error=f"Edge TTS error: {e}")
