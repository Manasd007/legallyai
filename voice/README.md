# Legally AI Voice — the voice service behind Legally AI

Real-time voice legal assistant for India. Speak a legal question in Hindi /
Hinglish / English; get a spoken answer grounded in 1,991 Indian Supreme Court
judgments (via the existing Legally AI RAG service), with citations mentioned
naturally in speech and a full written summary after the call.

**This is a headless service.** It runs as its own process and its own deploy —
deliberately *not* folded into `backend/`, because WebRTC needs sticky
long-lived connections and hard real-time CPU, while the backend is stateless
and already holds FAISS + InLegalBERT in memory. The UI is the mic button in
the Legally AI workspace composer (`frontend/components/VoiceCall.tsx`), which
calls this service directly across origins (see `ALLOWED_ORIGINS`).

Full product/architecture context: [NYAYAVOICE_PROJECT_CONTEXT.md](NYAYAVOICE_PROJECT_CONTEXT.md).
Change history and design rationale: [CHANGELOG.md](CHANGELOG.md).

## Architecture

Cascaded, fully streaming pipeline on [Pipecat](https://github.com/pipecat-ai/pipecat):

```
Browser mic ─ WebRTC ─→ Deepgram Nova-3 STT (multilingual, interim results)
    → transcript repair (legal-term normalization)
    → Silero VAD + Hinglish-adaptive endpointing
    → Groq Llama (tool: legal_search → Legally AI /api/retrieve)
    → Deepgram Aura-2 TTS ─ WebRTC ─→ browser playback (interruptible)
```

Side channels: live transcript over WebSocket, post-call summary with full
citations, per-turn P50/P95 telemetry (JSONL + `/api/metrics`). The frontend
renders the transcript and the summary; latency events are still published and
still recorded, they just have no HUD in the product UI.

## Run locally

Prereqs: Python 3.11+, the Legally AI backend running on `http://localhost:8000`
(its FAISS index built), Deepgram + Groq API keys (both free tier).

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows
cp .env.example .env                              # then fill in the two keys
.venv/Scripts/python -m uvicorn server.main:app --port 7860
```

Then run the Next.js frontend with `NEXT_PUBLIC_VOICE_URL=http://localhost:7860`,
open the workspace, and hit the mic button in the composer. `GET /api/health`
should report the `rag_base_url` you configured.

## Evals

```bash
.venv/Scripts/python -m evals.run_evals            # all suites
.venv/Scripts/python -m evals.run_evals --suite repair
```

Deterministic suites (`repair`, `interruption`) always run; suites needing the
Groq key or the RAG service skip with a reason when those are unavailable;
`latency` reads real telemetry from `data/telemetry/` and regresses against the
budget (≤800ms P50 / ≤1200ms P95 end-to-end).

## Repo layout

```
server/
  main.py               FastAPI + WebRTC entrypoint, event WS, metrics, summary
  config.py             every tunable + timeout in one place
  pipeline/             Pipecat assembly, endpointing, custom processors, session hub
  llm/                  system prompt, transcript repair, dialog state
  tools/legal_search.py client for the existing Legally AI RAG endpoint
  telemetry/            per-turn latency records, P50/P95, UI event bus
  summary.py            post-call text summary with full citations
evals/                  regression suite (§6 of the context doc)
vocab/legal_terms.txt   boosted legal vocabulary + repair substitutions
```
