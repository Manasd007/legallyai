from __future__ import annotations

import logging
import time
from pathlib import Path

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.deepgram.stt import DeepgramSTTService, DeepgramSTTSettings
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

from server.config import REPO_ROOT, get_settings
from server.llm.dialog_state import trim_history
from server.llm.languages import profile_for
from server.llm.prompts import LEGAL_SEARCH_DESCRIPTION, SYSTEM_PROMPT, pick_ack
from server.pipeline.edge_tts import EdgeTTSService
from server.pipeline.endpointing import build_turn_strategies
from server.pipeline.processors import (
    DeliveredTextTracker,
    FunctionCallMarkupFilter,
    GeneratedTextTracker,
    TranscriptRepairProcessor,
)
from server.pipeline.session import SessionHub
from server.telemetry.observer import TurnTelemetryObserver
from server.tools.legal_search import legal_search

log = logging.getLogger("legallyai.voice.builder")

VOCAB_PATH = REPO_ROOT / "vocab" / "legal_terms.txt"


def _boost_terms(path: Path = VOCAB_PATH, limit: int = 100) -> list[str]:
    if not path.exists():
        return []
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=>" not in line:
            terms.append(line)
    return terms[:limit]


def _sync_context_with_state(context: LLMContext, hub: SessionHub) -> None:
    state_block = hub.state.render()
    system_text = SYSTEM_PROMPT + (f"\n\n{state_block}" if state_block else "")
    messages = [m for m in context.get_messages() if m.get("role") != "system"]
    context.set_messages(trim_history([{"role": "system", "content": system_text}, *messages]))


def build_pipeline_worker(
    connection: SmallWebRTCConnection, hub: SessionHub
) -> PipelineWorker:
    s = get_settings()

    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )

    stt_settings = DeepgramSTTSettings(
        model=s.stt_model,
        language=s.stt_language,
        interim_results=True,
        smart_format=True,
        punctuate=True,
        numerals=True,
        keyterm=_boost_terms() if s.stt_language == "en" else None,
        endpointing=s.stt_endpointing_ms,
        utterance_end_ms=s.stt_utterance_end_ms,
    )
    stt = DeepgramSTTService(api_key=s.deepgram_api_key, settings=stt_settings)

    if s.tts_engine == "edge":
        tts = EdgeTTSService(
            voice=s.edge_tts_voice, rate=s.edge_tts_rate
        )

        def _on_language_changed(code: str) -> None:
            tts.set_voice_name(profile_for(code).voice)

        hub.on_language_changed = _on_language_changed
    else:
        tts = DeepgramTTSService(
            api_key=s.deepgram_api_key,
            settings=DeepgramTTSService.Settings(voice=s.tts_voice),
        )

    llm = GroqLLMService(
        api_key=s.groq_api_key,
        settings=GroqLLMService.Settings(
            model=s.groq_model, temperature=s.llm_temperature, max_completion_tokens=260
        ),
    )

    tools = ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name="legal_search",
                description=LEGAL_SEARCH_DESCRIPTION,
                properties={
                    "query": {
                        "type": "string",
                        "description": "Self-contained English description of the "
                        "legal issue, including act names and section numbers.",
                    }
                },
                required=["query"],
            )
        ]
    )
    context = LLMContext(
        messages=[{"role": "system", "content": SYSTEM_PROMPT}], tools=tools
    )

    async def _legal_search_handler(params: FunctionCallParams) -> None:
        query = str(params.arguments.get("query", "")).strip()
        hub.tool_called(query)
        await params.llm.push_frame(TTSSpeakFrame(pick_ack(hub.language)))
        t0 = time.perf_counter()
        result = await legal_search(query)
        hub.tool_finished(query, result, int((time.perf_counter() - t0) * 1000))
        await params.result_callback(result)

    llm.register_function("legal_search", _legal_search_handler)

    vad = SileroVADAnalyzer(
        params=VADParams(
            confidence=s.vad_confidence,
            start_secs=s.vad_start_secs,
            stop_secs=s.vad_stop_secs,
        )
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=vad,
            user_turn_strategies=build_turn_strategies(mode="adaptive"),
        ),
    )

    hub.on_turn_committed = lambda: _sync_context_with_state(context, hub)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            TranscriptRepairProcessor(hub),
            user_aggregator,
            llm,
            FunctionCallMarkupFilter(),
            tts,
            GeneratedTextTracker(hub),
            transport.output(),
            DeliveredTextTracker(hub),
            assistant_aggregator,
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        observers=[TurnTelemetryObserver(hub)],
    )

    @transport.event_handler("on_client_connected")
    async def _on_connected(transport, client) -> None:  # noqa: ANN001
        log.info("Client connected: session %s", hub.session_id)
        await worker.queue_frames([TTSSpeakFrame(profile_for(hub.language).greeting)])

    @transport.event_handler("on_client_disconnected")
    async def _on_disconnected(transport, client) -> None:  # noqa: ANN001
        log.info("Client disconnected: session %s", hub.session_id)
        await worker.cancel()

    return worker
