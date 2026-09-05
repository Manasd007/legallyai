create extension if not exists pgcrypto;

create table if not exists cases (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  title      text,
  raw_text   text not null,
  file_url   text,
  created_at timestamptz not null default now()
);

create index if not exists cases_user_idx on cases (user_id, created_at desc);

create table if not exists predictions (
  id             uuid primary key default gen_random_uuid(),
  case_id        uuid not null references cases (id) on delete cascade,
  likely_outcome text not null check (likely_outcome in ('Granted', 'Dismissed', 'Uncertain')),
  confidence     text not null check (confidence in ('low', 'medium', 'high')),
  model_version  text not null,
  created_at     timestamptz not null default now()
);

create index if not exists predictions_case_idx on predictions (case_id);

create table if not exists explanations (
  id            uuid primary key default gen_random_uuid(),
  prediction_id uuid not null references predictions (id) on delete cascade,
  summary_text  text not null default '',
  reasoning     text not null default '',
  cited_cases   jsonb not null default '[]'::jsonb,
  retrieved_ids jsonb not null default '[]'::jsonb,
  method        text,
  created_at    timestamptz not null default now()
);

create index if not exists explanations_prediction_idx on explanations (prediction_id);

create table if not exists feedback (
  id            uuid primary key default gen_random_uuid(),
  prediction_id uuid not null references predictions (id) on delete cascade,
  user_id       uuid not null references auth.users (id) on delete cascade,
  rating        smallint not null check (rating in (-1, 1)),
  note          text,
  created_at    timestamptz not null default now()
);

create index if not exists feedback_prediction_idx on feedback (prediction_id);
create index if not exists feedback_user_idx on feedback (user_id);

create table if not exists conversations (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  tool       text not null check (tool in ('predict', 'assistant', 'documents', 'statutes')),
  session_id uuid,
  title      text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists conversations_user_idx on conversations (user_id, updated_at desc);
create index if not exists conversations_session_idx on conversations (user_id, session_id);

create table if not exists messages (
  id              uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references conversations (id) on delete cascade,
  role            text not null check (role in ('user', 'assistant')),
  content         text not null default '',
  payload         jsonb,
  case_id         uuid references cases (id) on delete set null,
  created_at      timestamptz not null default now()
);

create index if not exists messages_conversation_idx on messages (conversation_id, created_at);
create index if not exists messages_case_idx on messages (case_id) where case_id is not null;

alter table cases         enable row level security;
alter table predictions   enable row level security;
alter table explanations  enable row level security;
alter table feedback      enable row level security;
alter table conversations enable row level security;
alter table messages      enable row level security;

drop policy if exists "own cases" on cases;
create policy "own cases" on cases
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own feedback" on feedback;
create policy "own feedback" on feedback
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own conversations" on conversations;
create policy "own conversations" on conversations
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own messages" on messages;
create policy "own messages" on messages
  for all using (
    exists (
      select 1 from conversations c
      where c.id = messages.conversation_id and c.user_id = auth.uid()
    )
  ) with check (
    exists (
      select 1 from conversations c
      where c.id = messages.conversation_id and c.user_id = auth.uid()
    )
  );

drop policy if exists "own predictions" on predictions;
create policy "own predictions" on predictions
  for select using (
    exists (
      select 1 from cases c
      where c.id = predictions.case_id and c.user_id = auth.uid()
    )
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
