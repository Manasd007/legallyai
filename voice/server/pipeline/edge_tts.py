"""Edge TTS service: natural Hindi/Hinglish voices at zero cost.

Deepgram Aura-2 has NO Hindi or Indian-accented voice (English voices are
US/UK/AU/IE/PH only), so it reads Hinglish like a foreigner — the exact
complaint from the first live-call test. Microsoft Edge neural voices include
native Hindi voices (hi-IN-SwaraNeural / hi-IN-MadhurNeural) that handle
Devanagari, romanized Hinglish AND embedded English legal terms naturally,
need no API key, and stream fast enough for conversation.

Edge streams MP3; Pipecat needs raw PCM. The MP3 packets are decoded
incrementally with PyAV (already installed via aiortc), so first audio goes
out as soon as the first packets arrive — no full-utterance buffering.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

import av
import edge_tts
from pipecat.frames.frames import ErrorFrame, Frame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService

EDGE_NATIVE_RATE = 24000  # audio-24khz-48kbitrate-mono-mp3


class EdgeTTSService(TTSService):
    """Streaming TTS on Microsoft Edge neural voices (keyless)."""

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
        """Switch the neural voice for subsequent utterances.

        `run_tts` reads `self._voice` per utterance, so this takes effect on the
        next thing spoken and never interrupts audio already streaming."""
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
            # Drain both decoder and resampler.
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
