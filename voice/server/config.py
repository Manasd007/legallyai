from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    deepgram_api_key: str = ""
    groq_api_key: str = ""

    groq_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.6
    stt_model: str = "nova-3"
    stt_language: str = "multi"
    stt_endpointing_ms: int = 400
    stt_utterance_end_ms: int = 1000

    tts_engine: str = "edge"
    edge_tts_voice: str = "hi-IN-SwaraNeural"
    edge_tts_rate: str = "+8%"
    tts_voice: str = "aura-2-asteria-en"

    rag_base_url: str = "http://localhost:8000"
    rag_timeout_s: float = 6.0
    rag_top_chunks: int = 4
    rag_excerpt_chars: int = 500
    rag_weak_similarity: float = 0.35

    vad_confidence: float = 0.7
    vad_start_secs: float = 0.2
    vad_stop_secs: float = 0.65
    endpoint_extra_patience_s: float = 0.6

    max_history_messages: int = 14
    summarize_after_messages: int = 20

    telemetry_dir: str = str(REPO_ROOT / "data" / "telemetry")
    latency_p50_target_ms: int = 800
    latency_p95_target_ms: int = 1200
    latency_hard_ceiling_ms: int = 1500
    stage_p95_budget_ms: dict[str, int] = {
        "endpoint_ms": 250,
        "stt_final_ms": 300,
        "llm_first_ms": 400,
        "tts_first_ms": 200,
        "e2e_ms": 1200,
    }

    host: str = "0.0.0.0"
    port: int = 7860
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    stun_url: str = "stun:stun.l.google.com:19302"
    turn_url: str = ""
    turn_username: str = ""
    turn_credential: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def ice_servers(self) -> list:
        from pipecat.transports.smallwebrtc.connection import IceServer

        servers: list = []
        if self.stun_url:
            servers.append(IceServer(urls=self.stun_url))
        if self.turn_url:
            servers.append(
                IceServer(
                    urls=self.turn_url,
                    username=self.turn_username or None,
                    credential=self.turn_credential or None,
                )
            )
        return servers


@lru_cache
def get_settings() -> Settings:
    return Settings()
