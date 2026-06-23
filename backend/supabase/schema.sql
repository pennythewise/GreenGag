-- =============================================================================
-- GreenGag — Supabase schema
-- Run in: Supabase Dashboard → SQL Editor
--
-- FIRST TIME:  run this file only.
-- RE-INSTALL:  run reset.sql, then this file.
--
-- Embeddings: OpenAI text-embedding-3-large with dimensions=2000
--   • Default large model output is 3072 dims → HNSW index FAILS on Supabase
--     (pgvector HNSW max = 2000 dimensions).
--   • Fix: pass dimensions=2000 in the OpenAI Embeddings API (same model,
--     Matryoshka-reduced vectors — still stronger than text-embedding-3-small).
--   • Backend .env: OPENAI_EMBEDDING_MODEL=text-embedding-3-large
--                    EMBEDDING_DIMENSIONS=2000
--
-- DO NOT use vector(3072) with HNSW on Supabase.
-- Alternative: vector(1536) + text-embedding-3-small (also valid, cheaper).
-- =============================================================================

-- ── Extensions ──────────────────────────────────────────────────────────────
create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

-- ── Enums ───────────────────────────────────────────────────────────────────
do $$ begin
  create type ingest_status as enum (
    'pending',
    'uploading',
    'chunking',
    'embedding',
    'ready',
    'failed'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type extract_status as enum (
    'pending',
    'retrieving',
    'extracting',
    'complete',
    'failed'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type esg_pillar as enum ('environment', 'social', 'governance');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type pillar_retrieval_status as enum (
    'ok',
    'insufficient_text_retrieved'
  );
exception when duplicate_object then null;
end $$;

-- ── Documents (PDF metadata + pipeline state) ───────────────────────────────
create table if not exists public.documents (
  id                uuid primary key default gen_random_uuid(),
  storage_path      text not null,
  original_filename text not null,
  content_hash        text,
  document_title    text,
  reporting_entity  text,
  reporting_year    text,
  ingest_status     ingest_status not null default 'pending',
  extract_status    extract_status not null default 'pending',
  chunk_count       integer not null default 0,
  claim_count       integer not null default 0,
  embedding_model   text not null default 'text-embedding-3-large',
  embedding_dims    integer not null default 2000,
  error_message     text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),

  constraint documents_embedding_dims_check check (embedding_dims > 0 and embedding_dims <= 2000)
);

create index if not exists documents_ingest_status_idx on public.documents (ingest_status);
create index if not exists documents_extract_status_idx on public.documents (extract_status);

-- One ready ingest per PDF bytes + embedding config (content-hash dedup)
create unique index if not exists documents_dedup_idx
  on public.documents (content_hash, embedding_model, embedding_dims)
  where ingest_status = 'ready' and content_hash is not null;

-- ── Document chunks (RAG store) ─────────────────────────────────────────────
-- vector(2000) = text-embedding-3-large + OpenAI API dimensions=2000
create table if not exists public.document_chunks (
  id              uuid primary key default gen_random_uuid(),
  document_id     uuid not null references public.documents (id) on delete cascade,
  chunk_index     integer not null,
  page            integer,
  section_heading text,
  pillar_hint     text,
  content         text not null,
  token_estimate  integer,
  embedding       extensions.vector(2000) not null,
  created_at      timestamptz not null default now(),

  constraint document_chunks_pillar_hint_check check (
    pillar_hint is null
    or pillar_hint in ('environment', 'social', 'governance', 'mixed')
  ),
  constraint document_chunks_unique_index unique (document_id, chunk_index)
);

create index if not exists document_chunks_document_id_idx
  on public.document_chunks (document_id);

-- HNSW cosine index (requires embedding_dims <= 2000 on Supabase)
create index if not exists document_chunks_embedding_hnsw_idx
  on public.document_chunks
  using hnsw (embedding extensions.vector_cosine_ops);

-- ── Extraction runs (audit trail per extract call) ────────────────────────────
create table if not exists public.extraction_runs (
  id               uuid primary key default gen_random_uuid(),
  document_id      uuid not null references public.documents (id) on delete cascade,
  pillar_status    jsonb not null default '{}'::jsonb,
  chunks_used      jsonb not null default '[]'::jsonb,
  extraction_notes text[] not null default '{}',
  model            text,
  embedding_model  text,
  embedding_dims   integer,
  created_at       timestamptz not null default now()
);

create index if not exists extraction_runs_document_id_idx
  on public.extraction_runs (document_id);

-- ── Claims (extended ExtractedClaim contract) ───────────────────────────────
create table if not exists public.claims (
  id                  text not null,
  document_id         uuid not null references public.documents (id) on delete cascade,
  extraction_run_id   uuid references public.extraction_runs (id) on delete set null,

  pillar              esg_pillar not null,
  category            text not null,
  claim_type          text not null,
  label               text not null,
  raw_text            text not null,
  entity              text,
  metric              text,
  target_value        text,
  achieved_value      text,
  baseline_value      text,
  time_period         text,
  location            text,
  unit                text,
  page                integer,
  section_heading     text,
  key_metrics         jsonb not null default '{}'::jsonb,
  confidence          numeric(4, 3) check (confidence >= 0 and confidence <= 1),

  claimed_reduction_pct numeric,
  material_class        text,
  stated_spend_usd      numeric,
  highlight             jsonb,

  created_at            timestamptz not null default now(),

  primary key (document_id, id)
);

create index if not exists claims_document_id_idx on public.claims (document_id);
create index if not exists claims_pillar_idx on public.claims (pillar);
create index if not exists claims_claim_type_idx on public.claims (claim_type);

-- ── Evidence (agent hits per claim) ───────────────────────────────────────────
create table if not exists public.evidence (
  id                  uuid primary key default gen_random_uuid(),
  document_id         uuid not null references public.documents (id) on delete cascade,
  claim_id            text not null,
  agent_key           text not null,
  classification      text not null,
  summary             text not null,
  source_url          text,
  source_label        text,
  contradiction_score numeric(4, 3),
  confidence          numeric(4, 3),
  rationale_trail     text[] not null default '{}',
  payload             jsonb not null default '{}'::jsonb,
  created_at          timestamptz not null default now(),

  constraint evidence_claim_fk
    foreign key (document_id, claim_id)
    references public.claims (document_id, id)
    on delete cascade,

  constraint evidence_classification_check check (
    classification in ('supports', 'contradicts', 'insufficient', 'irrelevant')
  )
);

create index if not exists evidence_document_claim_idx
  on public.evidence (document_id, claim_id);

-- ── Media / news cache ────────────────────────────────────────────────────────
create table if not exists public.media_articles (
  id                  uuid primary key default gen_random_uuid(),
  document_id         uuid references public.documents (id) on delete set null,
  claim_id            text,
  headline            text not null,
  source              text not null,
  url                 text not null,
  published           date,
  snippet             text,
  contradiction_score numeric(4, 3),
  tag                 text,
  fetched_at          timestamptz not null default now(),

  constraint media_articles_url_unique unique (url)
);

create index if not exists media_articles_document_id_idx
  on public.media_articles (document_id);

-- ── updated_at trigger ──────────────────────────────────────────────────────
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists documents_updated_at on public.documents;
create trigger documents_updated_at
  before update on public.documents
  for each row execute function public.set_updated_at();

-- ── RAG: hybrid vector search (pillar boost, no LLM chat) ─────────────────────
create or replace function public.match_document_chunks(
  p_document_id       uuid,
  p_query_embedding   extensions.vector(2000),
  p_pillar            text,
  p_match_count       integer default 8
)
returns table (
  id              uuid,
  content         text,
  page            integer,
  section_heading text,
  pillar_hint     text,
  vector_score    double precision,
  hybrid_score    double precision
)
language sql
stable
as $$
  select
    dc.id,
    dc.content,
    dc.page,
    dc.section_heading,
    dc.pillar_hint,
    (1 - (dc.embedding <=> p_query_embedding))::double precision as vector_score,
    (
      (1 - (dc.embedding <=> p_query_embedding))
      * case
          when dc.pillar_hint = p_pillar then 1.0
          when dc.pillar_hint is null or dc.pillar_hint = 'mixed' then 0.85
          else 0.5
        end
    )::double precision as hybrid_score
  from public.document_chunks dc
  where dc.document_id = p_document_id
  order by hybrid_score desc
  limit p_match_count;
$$;

-- ── Supabase Storage bucket for PDFs ────────────────────────────────────────
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'documents',
  'documents',
  false,
  52428800,
  array['application/pdf']
)
on conflict (id) do nothing;

drop policy if exists "Service role full access on documents bucket" on storage.objects;
create policy "Service role full access on documents bucket"
  on storage.objects
  for all
  to service_role
  using (bucket_id = 'documents')
  with check (bucket_id = 'documents');

-- ── Row Level Security ────────────────────────────────────────────────────────
alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;
alter table public.extraction_runs enable row level security;
alter table public.claims enable row level security;
alter table public.evidence enable row level security;
alter table public.media_articles enable row level security;

drop policy if exists "Service role all on documents" on public.documents;
create policy "Service role all on documents"
  on public.documents for all to service_role
  using (true) with check (true);

drop policy if exists "Service role all on document_chunks" on public.document_chunks;
create policy "Service role all on document_chunks"
  on public.document_chunks for all to service_role
  using (true) with check (true);

drop policy if exists "Service role all on extraction_runs" on public.extraction_runs;
create policy "Service role all on extraction_runs"
  on public.extraction_runs for all to service_role
  using (true) with check (true);

drop policy if exists "Service role all on claims" on public.claims;
create policy "Service role all on claims"
  on public.claims for all to service_role
  using (true) with check (true);

drop policy if exists "Service role all on evidence" on public.evidence;
create policy "Service role all on evidence"
  on public.evidence for all to service_role
  using (true) with check (true);

drop policy if exists "Service role all on media_articles" on public.media_articles;
create policy "Service role all on media_articles"
  on public.media_articles for all to service_role
  using (true) with check (true);

-- ── View: claims summary per document ───────────────────────────────────────
create or replace view public.document_claims_summary as
select
  d.id as document_id,
  d.original_filename,
  d.ingest_status,
  d.extract_status,
  d.chunk_count,
  d.embedding_model,
  d.embedding_dims,
  count(c.id) as claim_count,
  count(c.id) filter (where c.pillar = 'environment') as environment_claims,
  count(c.id) filter (where c.pillar = 'social') as social_claims,
  count(c.id) filter (where c.pillar = 'governance') as governance_claims
from public.documents d
left join public.claims c on c.document_id = d.id
group by d.id;

-- ── Migration: content-hash dedup (safe to re-run on existing projects) ─────
alter table public.documents add column if not exists content_hash text;

drop index if exists public.documents_dedup_idx;
create unique index if not exists documents_dedup_idx
  on public.documents (content_hash, embedding_model, embedding_dims)
  where ingest_status = 'ready' and content_hash is not null;
