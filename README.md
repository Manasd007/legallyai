# Legally AI

> A research/educational legal judgment **prediction & explanation** assistant for Indian law.
> **Not legal advice.** Consult a qualified advocate before acting on anything here.

A user describes a legal situation; the system retrieves the most relevant past Indian
cases and statutes, predicts the likely outcome, and explains its reasoning **grounded
only in those retrieved sources** — with every citation verified against real documents.

## What it does
1. **Intake router** — classifies the question as `legal` / `general_legal` / `not_legal`.
2. **Reformulate** — rewrites the layperson situation into a legal-issue statement.
3. **Retrieve** — hybrid (vector + keyword) top-k over indexed judgments + statutes.
4. **Predict + explain** — single grounded LLM call: diagnose → forecast → explain.
5. **Verify citations** — every cited case must exist in the retrieved set, else strip/hedge.
6. **Persist** — query, prediction, explanation, retrieved IDs, and user feedback.

## What it does NOT do
- Give definitive legal advice or guarantee outcomes.
- Invent or "remember" cases not in the corpus.
- Cite specific case law in the general-legal path.
- Handle confidential documents on free tiers.

## Architecture (two phases)
- **Build-time (offline, free GPU):** download corpus → role-aware chunk + embed (InLegalBERT) → build FAISS index. See `pipeline/`.
- **Runtime (free CPU + free API tiers):** FastAPI backend (`backend/`) + Next.js frontend (`frontend/`).

## v1 decisions
| Choice | Value |
|---|---|
| Embeddings | `law-ai/InLegalBERT` (768-dim) |
| Vector store | local **FAISS** (served from FastAPI) |
| Corpus | Supreme Court judgments, last ~10 years |
| Router LLM | Groq (fast Llama) |
| Reasoning LLM | Google AI Studio / Gemini Flash |
| Auth + DB | Supabase (Auth + Postgres) |

## Repo layout
```
legally-ai/
├── frontend/     Next.js + Tailwind (Vercel)
├── backend/      FastAPI app (Render / HF Space)
│   └── prompts/  versioned prompt templates
├── pipeline/     offline corpus download + chunk/embed (Kaggle/Colab)
├── sql/          Postgres schema
└── .env.example
```

## Quickstart (backend, local)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv/Scripts/activate
pip install -r requirements.txt
cp ../.env.example .env        # fill in keys
uvicorn main:app --reload
```
Then: `curl -X POST localhost:8000/api/query -H 'content-type: application/json' -d '{"question":"..."}'`

## Build phases
- [x] **Phase 0** — corpus pipeline scaffolding (`pipeline/`)
- [x] **Phase 1** — retrieval API (`POST /api/query` returns top-k, no prediction yet)
- [ ] **Phase 2** — grounded prediction + citation verification
- [ ] **Phase 3** — intake router (legal / general / non-legal)
- [ ] **Phase 4** — frontend + Supabase auth + history/feedback + cache
- [ ] **Phase 5** — evaluate against PredEx + deploy

## Attribution
- Court-judgment data is **CC-BY-4.0** — credit the source dataset (Open Justice India / `vanga/indian-supreme-court-judgments`).
- PredEx / ILDC and InLegalBERT are research artifacts — cite their papers if you publish results.
