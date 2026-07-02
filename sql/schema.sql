-- Legally AI — Postgres / Supabase schema (brief §8)
-- Users are handled by Supabase Auth (auth.users); we reference auth.uid().
-- Run in the Supabase SQL editor.

-- ── User-submitted situations ────────────────────────────────
create table if not exists cases (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  title       text,
  raw_text    text not null,          -- the user's submitted situation
  file_url    text,                   -- optional uploaded PDF
  created_at  timestamptz default now()
);

-- ── Predictions ──────────────────────────────────────────────
create table if not exists predictions (
  id             uuid primary key default gen_random_uuid(),
  case_id        uuid not null references cases(id) on delete cascade,
  likely_outcome text not null,        -- Granted | Dismissed | Uncertain
  confidence     text not null,        -- low | medium | high
  model_version  text not null,
  created_at     timestamptz default now()
);

-- ── Explanations ─────────────────────────────────────────────
create table if not exists explanations (
  id             uuid primary key default gen_random_uuid(),
  prediction_id  uuid not null references predictions(id) on delete cascade,
  summary_text   text not null,
  reasoning      text not null,
  cited_cases    jsonb not null,       -- [{case_name, citation, relevance}]
  retrieved_ids  jsonb not null,       -- ids/citations of retrieved docs (audit trail)
  method         text,                 -- e.g. "gemini-rag-v1"
  created_at     timestamptz default now()
);

-- ── Feedback ─────────────────────────────────────────────────
create table if not exists feedback (
  id             uuid primary key default gen_random_uuid(),
  prediction_id  uuid not null references predictions(id) on delete cascade,
  user_id        uuid not null references auth.users(id) on delete cascade,
  rating         smallint not null,    -- +1 / -1
  note           text,
  created_at     timestamptz default now()
);

-- ── Conversation threads (the returning-user "chat sections") ────
-- One row per sidebar entry. Groups an ongoing exchange in a single tool so a
-- returning user reopens the whole thread, like Claude's chat list. The
-- cases/predictions tables above stay as the prediction audit trail; this layer
-- is the user-facing history. A predict turn can link back via messages.case_id.
create table if not exists conversations (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  tool        text not null,            -- predict | assistant | documents | statutes
  session_id  uuid,                     -- groups the per-tool threads of one workspace session (null = legacy singleton)
  title       text,                     -- auto-set from the first user message
  created_at  timestamptz default now(),
  updated_at  timestamptz default now() -- bumped on each new turn → sort sidebar by recency
);

-- Existing databases: add the grouping column + index without a full rebuild.
alter table conversations add column if not exists session_id uuid;

create index if not exists conversations_user_idx
  on conversations (user_id, updated_at desc);

-- One workspace "session" spans up to three per-tool threads, linked by session_id.
-- The sidebar lists sessions (not raw threads), so we group by (user_id, session_id).
create index if not exists conversations_session_idx
  on conversations (user_id, session_id);

-- Every turn in a thread: the user's message or the assistant's reply. `payload`
-- holds the full structured response (win_probability, cited_cases, verification…)
-- so a past prediction card re-renders exactly as it did live.
create table if not exists messages (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations(id) on delete cascade,
  role            text not null,        -- user | assistant
  content         text not null,        -- plain text (the question, or the answer prose)
  payload         jsonb,                -- full structured response, if any
  case_id         uuid references cases(id) on delete set null,  -- link to the audit row (predict)
  created_at      timestamptz default now()
);

create index if not exists messages_conversation_idx
  on messages (conversation_id, created_at);

-- ── Vector store for the corpus (built offline; NOT user data) ─
-- NOTE: v1 uses local FAISS served from FastAPI, so this table is
-- OPTIONAL (only needed if VECTOR_BACKEND=pgvector). Kept here for
-- the pgvector path. If the index outgrows the free DB, store
-- embeddings in FAISS and keep only metadata here (brief §5).
create extension if not exists vector;

create table if not exists corpus_chunks (
  id           uuid primary key default gen_random_uuid(),
  case_name    text,
  citation     text,
  court        text,
  year         int,
  outcome      text,
  segment_role text,                   -- Facts | Issues | Arguments | Ratio | ...
  chunk_text   text not null,
  embedding    vector(768)             -- match EMBEDDING_DIM
);

create index if not exists corpus_chunks_embedding_idx
  on corpus_chunks using ivfflat (embedding vector_cosine_ops);

-- Postgres full-text index for the keyword leg of hybrid search.
create index if not exists corpus_chunks_fts_idx
  on corpus_chunks using gin (to_tsvector('english', chunk_text));

-- ── Row Level Security ───────────────────────────────────────
-- Users may only read/write their own rows. corpus_chunks is public read-only.
alter table cases         enable row level security;
alter table predictions   enable row level security;
alter table explanations  enable row level security;
alter table feedback      enable row level security;
alter table conversations enable row level security;
alter table messages      enable row level security;

-- Policies are dropped-then-created so the whole file stays safe to re-run
-- (Postgres has no `create policy if not exists`).
drop policy if exists "own cases" on cases;
create policy "own cases" on cases
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own feedback" on feedback;
create policy "own feedback" on feedback
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own conversations" on conversations;
create policy "own conversations" on conversations
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Messages are reachable only through a conversation the user owns.
drop policy if exists "own messages" on messages;
create policy "own messages" on messages
  for all using (
    exists (select 1 from conversations c where c.id = messages.conversation_id and c.user_id = auth.uid())
  ) with check (
    exists (select 1 from conversations c where c.id = messages.conversation_id and c.user_id = auth.uid())
  );

-- Predictions/explanations are reachable only via a case the user owns.
drop policy if exists "own predictions" on predictions;
create policy "own predictions" on predictions
  for select using (
    exists (select 1 from cases c where c.id = predictions.case_id and c.user_id = auth.uid())
  );

drop policy if exists "own explanations" on explanations;
create policy "own explanations" on explanations
  for select using (
    exists (
      select 1 from predictions p
      join cases c on c.id = p.case_id
      where p.id = explanations.prediction_id and c.user_id = auth.uid()
    )
  );
