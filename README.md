# Legally AI

**A precedent-grounded legal assistant for Indian law.** Describe a legal situation in plain
words - or upload a contract, notice, or court order - and get an assessment of where you
stand, grounded in how real Supreme Court judgments were decided, with **every citation
verified against the indexed corpus** so nothing is invented.

> Research/educational tool, not legal advice.

---

## Features

### ⚖️ Case assessment with a win/lose estimate
Describe what happened and get a plain-language read on your position: how likely the claim
is to succeed, **which facts help or hurt you** (each tied to a precedent-grounded reason),
and **concrete steps that would strengthen the case** - not just a probability, a strategy.

### 🔍 Every citation is real - and provable
The industry's biggest credibility problem is AI-invented case law. Here, every case the
model cites is checked against the retrieved corpus; anything unverifiable is stripped.
Each citation expands to the **verbatim source passage** from the actual judgment, and one
click opens the **full judgment with the relied-upon passage highlighted in context**.

### 📄 Document analysis with OCR
Upload a PDF, DOCX, image, or scan (handwriting included - OCR runs through a vision LLM,
no Tesseract). The analyzer returns where you stand, deadlines with urgency levels, amounts,
obligations, risks, recommended actions, and an auto-extracted **plain-English glossary** of
the legal jargon found in the document. Then chat with the document - answers are grounded
only in its text and cite the specific clause.

### 💬 Legal Q&A with cited answers
Conversational RAG over the case-law corpus. Follow-up questions carry context, every answer
lists the judgments it relied on, and a per-turn intake classifier keeps greetings and
meta-questions from triggering bogus retrieval.

### 📚 Statute finder
From a plain-language situation to the governing Acts and sections - each explained in
everyday language and linked to real judgments that applied it. The model is forbidden from
fabricating section numbers: it prefers provisions that appear in the retrieved cases.

### 🎙 Talk to it instead of typing
A mic button in the composer opens a real-time voice conversation in Hindi, English or
Hinglish - interruptible, grounded in the same judgments, answering out loud. Hang up and
the written summary with citations lands in the chat you were already having, so the
matter carries straight on in text.

### 🗂 One workspace, one matter
The three tools share a session: describe your situation once and it follows you across
tabs. Voice is a fourth way into the same matter, not a separate silo. Sessions persist
per user (Supabase auth + Postgres with row-level security), with full history restore.

---

## The prediction method (the interesting part)

Never ship a bare LLM guess. The win/lose estimate is a **three-signal ensemble** that
scores its own confidence by how much the signals *agree*:

| Signal | What it is |
|---|---|
| **Precedent vote** | Similarity-weighted vote over the *real recorded outcomes* of the most analogous retrieved cases |
| **Trained classifier** | InLegalBERT fine-tuned on PredEx (10.9k labeled Indian judgments) for binary applicant-wins prediction |
| **LLM forecast** | A grounded reasoning pass over the retrieved judgments - allowed to abstain |

The signals are blended into a final probability, and confidence is set by **agreement**:
all three point the same way → high; two of three → medium; divergence, abstention, or weak
retrieval → low, stated explicitly. When the system isn't sure, it says so instead of
sounding sure.

**Classifier evaluation** (held-out PredEx test split, n=1,217): accuracy **0.610**,
macro-F1 **0.605** - at the ceiling of the realistic band for a 512-token encoder on this
benchmark, and independently confirmed by a cross-dataset retrain on NyayaAnumana. The
ensemble design means no single weak signal can overclaim.

---

## Architecture

Two phases, so the runtime stays free-tier friendly:

```
BUILD TIME (offline, GPU)                      RUNTIME (CPU + free API tiers)
─────────────────────────                      ──────────────────────────────
AWS Open Data SC judgments                     Next.js frontend (Vercel)
  → PDF text extraction                          → /api/* proxied to FastAPI
  → role-aware chunking                        FastAPI backend
    (Facts/Issues/Ratio/Holding)                 → intake router → reformulate
  → InLegalBERT embeddings                       → FAISS retrieval (cosine)
  → FAISS index (88,988 vectors)                 → ensemble predict + verify
  → classifier fine-tune (PredEx)                → Supabase (auth + history)
  → artifacts pushed to HF Hub  ────────────►    artifacts pulled on startup
```

- **Corpus:** 1,991 Indian Supreme Court judgments (2015–2024, CC-BY-4.0), chunked into
  88,988 role-tagged passages. Ratio/Holding segments are up-weighted - they carry the
  decided outcome.
- **Artifacts on Hugging Face Hub**, version-pinned: the backend downloads the index and
  classifier on first boot ([corpus index](https://huggingface.co/datasets/ManasDubey/legally-ai-corpus-index) ·
  [classifier](https://huggingface.co/ManasDubey/legally-ai-predex-classifier)). Corpus
  expansion is a one-env-var bump (`CORPUS_REVISION=v2`), no code change.
- **LLM routing** through LiteLLM: fast Llama on Groq for the router/reformulator, a larger
  Groq model for grounded reasoning, with configurable fallback. All model IDs live in env
  config - free tiers change, logic doesn't.
- **Prompt-injection defense** on uploads: untrusted-document delimiters with sanitization,
  a server-side injection heuristic, and prompts that treat document text as inert data.
- **Voice is a third process**, not a third module. A fully streaming Pipecat pipeline -
  `mic → Deepgram Nova-3 STT → transcript repair → Silero VAD + Hinglish-adaptive endpointing
  → Groq Llama (tool: legal_search → POST /api/retrieve) → Edge TTS → speaker` - runs a
  real-time, interruptible conversation in Hindi, English or Hinglish under a **≤800 ms P50 /
  ≤1200 ms P95 end-to-end** budget, with per-turn P50/P95 telemetry. Those deadlines mean it
  can't share a core with FAISS + InLegalBERT, and its sticky WebRTC connections don't fit the
  backend's stateless horizontal scaling. It calls `/api/retrieve` rather than `/api/chat` -
  retrieval returns raw chunks with no nested LLM call, so the voice model composes the spoken
  answer itself instead of paying a second round-trip mid-sentence. On hang-up it posts a
  written summary with verified citations to `/api/voice/record`, which files it into the tab's
  thread so the matter continues in text.

---

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router), Tailwind, Framer Motion, three.js ambient shader |
| Backend | FastAPI, LiteLLM (Groq / Gemini / OpenRouter), FAISS, PyMuPDF |
| Voice | Pipecat streaming pipeline over aiortc/WebRTC · Deepgram Nova-3 STT (multilingual) · Silero VAD + Hinglish-adaptive endpointing · legal-term transcript repair · Groq Llama 3.3 70B · Edge TTS (`hi-IN-SwaraNeural`, native Hindi) |
| ML | InLegalBERT embeddings (768-d) + PredEx-fine-tuned classifier (PyTorch/Transformers) |
| Data | Supabase (Auth + Postgres + RLS), Hugging Face Hub for artifacts |
| Pipeline | boto3 (AWS Open Data), Colab notebooks for GPU builds |

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /api/query` | Full assessment: route → reformulate → retrieve → predict → verify |
| `POST /api/chat` | Conversational case-law Q&A (per-turn intake: smalltalk / general / grounded) |
| `POST /api/statutes` | Governing Acts & sections for a situation |
| `POST /api/doc/analyze` | Upload + extract (OCR fallback) + advisory breakdown |
| `POST /api/doc/chat` · `/api/doc/term` | Document-grounded chat and term explanations |
| `POST /api/case` | Full judgment reconstruction with the cited passage flagged |
| `POST /api/retrieve` | Raw reformulate + retrieve, no prediction - the seam the voice service calls |
| `POST /api/voice/record` | File a finished voice call into the session's Q&A thread |
| `GET/POST /api/sessions*` | Per-user session history (Supabase-backed) |

The voice service runs its own API on port 7860 (`POST /api/offer` for WebRTC signalling,
`WS /ws/events/{session}` for live transcript, `POST /api/summary/{session}` for the post-call
summary, plus `GET /api/health` and `GET /api/metrics` for readiness and P50/P95 latency). The
browser reaches it directly - Next.js rewrites don't proxy WebSockets.

---

## Run it locally

**Backend** (Python 3.11):
```bash
cd backend
python -m venv .venv && .venv/Scripts/activate    # Linux/mac: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env                           # add GROQ_API_KEY; Supabase optional locally
uvicorn main:app --port 8000
```
Without local index files, set `HF_NAMESPACE=ManasDubey` in `.env` and the backend pulls the
corpus index + classifier from the Hub on startup. Auth is skipped locally when Supabase
isn't configured.

**Frontend:**
```bash
cd frontend
npm install
cp .env.local.example .env.local                  # Supabase public keys (optional locally)
npm run dev
```

**Voice** (optional - the mic button hides itself if `NEXT_PUBLIC_VOICE_URL` is unset):
```bash
cd voice
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp .env.example .env                              # DEEPGRAM_API_KEY + GROQ_API_KEY
.venv/Scripts/python -m uvicorn server.main:app --port 7860
```
Runs as its own process on purpose: WebRTC needs sticky, long-lived connections and
real-time CPU, while the backend is stateless and already holds FAISS + InLegalBERT in
memory. It reaches the backend over `RAG_BASE_URL` and needs the frontend origin in
`ALLOWED_ORIGINS`.

## Repository layout

```
backend/     FastAPI app - retrieval, ensemble, verification, docs, Q&A, statutes
  prompts/   versioned prompt templates (system/user split, grounding rules)
frontend/    Next.js app - landing page + tabbed workspace
voice/       Legally AI Voice - real-time Hinglish voice agent (Pipecat/WebRTC), own process
pipeline/    offline: corpus download, chunk/embed/index, classifier training + eval
sql/         Supabase schema (row-level security)
huggingface/ README cards for the hosted artifacts
samples/     sample legal documents for trying the document analyzer
```

## Data & attribution

- Judgments from the [Indian Supreme Court Judgments](https://registry.opendata.aws/indian-supreme-court-judgments/)
  AWS Open Data collection (Open Justice India, **CC-BY-4.0**).
- [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) (MIT) ·
  [PredEx](https://huggingface.co/datasets/L-NLProc/PredEx) (Apache-2.0, [paper](https://arxiv.org/abs/2406.04136)).
- Hosted artifacts: corpus index (CC-BY-4.0) · classifier (Apache-2.0).
