"""Legally AI Voice server configuration.

All tunables live here so latency experiments are config changes, not code
changes (context doc §3: "measure before optimizing"). Every external call the
pipeline makes has its timeout defined in this file — no ad-hoc timeouts
scattered around the codebase.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # ── Service keys ─────────────────────────────────────────
    deepgram_api_key: str = ""
    groq_api_key: str = ""

    # ── Models ───────────────────────────────────────────────
    # Groq chosen for token speed (context doc §2). 8b-instant was tried first
    # for latency but it writes tool calls as literal text instead of using
    # the function-calling interface (live-call test, 2026-07-20) — the JSON
    # got spoken aloud and legal_search never actually ran. 70b-versatile does
    # proper tool calling and is still fast on Groq; the markup filter in the
    # pipeline remains as defense in depth.
    groq_model: str = "llama-3.3-70b-versatile"
    # 0.3 caused mode collapse in the live test: the model opened four turns in
    # a row with the identical "…ji, Supreme Court ne ek case mein kaha hai"
    # template. Factual grounding comes from the tool results, not from a cold
    # temperature — 0.6 buys natural variety without loosening legal claims.
    llm_temperature: float = 0.6
    stt_model: str = "nova-3"  # Deepgram Nova-3: multilingual, code-switching
    stt_language: str = "multi"  # Hindi + English code-switched input
    # Silence (ms) before Deepgram finalises a transcript segment. Its default
    # (~10ms) splits one sentence across several finals, so the LLM sees a turn
    # as fragments. This does NOT decide when the user's turn is over — Silero
    # VAD plus the Hinglish endpointer below own that.
    stt_endpointing_ms: int = 400
    # Emits an UtteranceEnd event on this much silence, which makes final
    # segmentation robust when a word is clipped. Deepgram's suggested floor.
    stt_utterance_end_ms: int = 1000

    # ── TTS ──────────────────────────────────────────────────
    # "edge" = Microsoft Edge neural voices (keyless): the only zero-budget
    # option with NATIVE Hindi voices. Deepgram Aura-2 has no Hindi or Indian
    # accent at all, so it mangles Hinglish ("foreigner reading Hindi" —
    # live-call feedback). "deepgram" kept for English-only experiments.
    tts_engine: str = "edge"
    edge_tts_voice: str = "hi-IN-SwaraNeural"  # or hi-IN-MadhurNeural (male)
    edge_tts_rate: str = "+8%"  # slightly brisk: closer to Indian speech tempo
    tts_voice: str = "aura-2-asteria-en"  # Deepgram fallback voice

    # ── RAG backend (existing Legally AI FastAPI service) ────
    # We call /api/retrieve, NOT /api/chat: retrieve returns raw chunks with no
    # nested LLM call, so the voice LLM composes the spoken answer itself and we
    # avoid paying a second model round-trip inside the tool call.
    rag_base_url: str = "http://localhost:8000"
    rag_timeout_s: float = 6.0  # hard timeout; on expiry the agent SAYS so
    rag_top_chunks: int = 4  # chunks forwarded to the LLM (token budget)
    rag_excerpt_chars: int = 500  # per-chunk excerpt cap (token budget)
    # Below this max_similarity the agent must hedge/refuse (mirrors the
    # weak-retrieval threshold used by Legally AI's verify step).
    rag_weak_similarity: float = 0.35

    # ── Turn detection / endpointing (context doc §4.1) ──────
    vad_confidence: float = 0.7
    vad_start_secs: float = 0.2
    # Base silence before we consider the turn over. Hinglish speakers pause
    # mid-sentence hunting for English legal words, so the gate below extends
    # this when the partial transcript looks incomplete.
    vad_stop_secs: float = 0.65
    endpoint_extra_patience_s: float = 0.6  # added when utterance looks unfinished

    # ── Context budget (context doc §4.9) ────────────────────
    max_history_messages: int = 14  # recent turns kept verbatim
    summarize_after_messages: int = 20  # roll older turns into the state block

    # ── Telemetry ────────────────────────────────────────────
    telemetry_dir: str = str(REPO_ROOT / "data" / "telemetry")
    # Latency budget (context doc §3) — the eval suite regresses on these.
    latency_p50_target_ms: int = 800
    latency_p95_target_ms: int = 1200
    latency_hard_ceiling_ms: int = 1500
    # Per-stage P95 ceilings (context doc §3 table, upper bounds). The latency
    # eval regresses each stage against these so we can "optimize the worst
    # stage, not the total" (§3.4). tool_ms is deliberately absent: the spoken
    # ack plays *during* the RAG round-trip (§3.2), so it is outside the
    # user-perceived e2e chain and must not gate a deploy.
    stage_p95_budget_ms: dict[str, int] = {
        "endpoint_ms": 250,
        "stt_final_ms": 300,
        "llm_first_ms": 400,
        "tts_first_ms": 200,
        "e2e_ms": 1200,
    }

    # ── Server ───────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 7860  # HF Spaces default; also fine locally
    # Origins allowed to open a call. The browser talks to this service
    # DIRECTLY (not through a Next.js rewrite — those don't proxy WebSockets),
    # so the frontend origin must be listed here. Comma-separated; kept as a
    # plain str because pydantic-settings would demand JSON for a list field.
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
