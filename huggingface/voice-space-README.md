---
title: Legally AI Voice
emoji: 🎙
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Legally AI Voice - voice service

Real-time voice legal assistant for India (Hindi / English / Hinglish), the voice tier behind
[Legally AI](https://github.com/Manasd007/legallyai). A call streams
`mic -> Deepgram Nova-3 STT -> Silero VAD + Hinglish-adaptive endpointing -> Groq Llama
(tool: legal_search -> backend /api/retrieve) -> Edge TTS -> speaker`, interruptible, with a
written summary and verified citations posted back to the app after the call.

Runs as its own process on purpose: WebRTC needs sticky, long-lived connections, so it is
deployed separately from the stateless FastAPI backend.

Required Space secrets: `DEEPGRAM_API_KEY`, `GROQ_API_KEY`, `RAG_BASE_URL` (the backend Space
URL, e.g. `https://manasdubey-legally-ai-api.hf.space`), and `ALLOWED_ORIGINS` (the frontend
origin, e.g. `https://<your-app>.vercel.app`).

> Research/educational tool, not legal advice.
