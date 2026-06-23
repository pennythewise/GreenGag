-- =============================================================================
-- GreenGag — Supabase RESET (run before schema.sql if re-installing)
-- Drops all GreenGag objects so schema.sql can run cleanly.
-- =============================================================================

drop view if exists public.document_claims_summary;

drop function if exists public.match_document_chunks(uuid, extensions.vector, text, integer);
drop function if exists public.match_document_chunks(uuid, extensions.vector(2000), text, integer);
drop function if exists public.match_document_chunks(uuid, extensions.vector(3072), text, integer);
drop function if exists public.match_document_chunks(uuid, extensions.vector(1536), text, integer);

drop trigger if exists documents_updated_at on public.documents;
drop function if exists public.set_updated_at();

drop table if exists public.evidence cascade;
drop table if exists public.media_articles cascade;
drop table if exists public.claims cascade;
drop table if exists public.extraction_runs cascade;
drop table if exists public.document_chunks cascade;
drop table if exists public.documents cascade;

drop type if exists public.pillar_retrieval_status cascade;
drop type if exists public.esg_pillar cascade;
drop type if exists public.extract_status cascade;
drop type if exists public.ingest_status cascade;

-- Storage policies (bucket row kept; re-created by schema.sql if missing)
drop policy if exists "Service role full access on documents bucket" on storage.objects;
