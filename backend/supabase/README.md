# Supabase setup

## Embedding dimensions (important)

Supabase **HNSW indexes support max 2000 dimensions**.  
`text-embedding-3-large` defaults to **3072** → index creation fails.

**Solution (used in this schema):**

| Setting | Value |
|---|---|
| Model | `text-embedding-3-large` |
| OpenAI API param | `dimensions=2000` |
| Postgres column | `vector(2000)` |

OpenAI Matryoshka embeddings let you use the **large** model at reduced dimension — still typically better than `text-embedding-3-small` at 1536.

```python
# Backend must pass dimensions=2000 on every embed call
client.embeddings.create(
    model="text-embedding-3-large",
    input=text,
    dimensions=2000,
)
```

## 1. Create project

Create a project at [supabase.com](https://supabase.com).

## 2. Run schema

**First install:** run [`schema.sql`](./schema.sql) in **SQL Editor**.

**Re-install** (after a failed run or dimension change):

1. Run [`reset.sql`](./reset.sql)
2. Run [`schema.sql`](./schema.sql)

**Existing project (add content-hash dedup):** re-run the migration block at the bottom of [`schema.sql`](./schema.sql) in SQL Editor (safe to re-run).

## 3. Environment variables

Copy to repo root `.env`:

```bash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

OPENAI_EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=2000
RAG_SIMILARITY_THRESHOLD=0.55
RAG_TOP_K_PER_PILLAR=8
RAG_MAX_CHUNKS_TO_LLM=20
```

## 4. Verify

```sql
select * from storage.buckets where id = 'documents';
select proname from pg_proc where proname = 'match_document_chunks';

-- Confirm column type
select column_name, udt_name
from information_schema.columns
where table_name = 'document_chunks' and column_name = 'embedding';
```

## 5. Optional: rebuild HNSW after bulk chunk insert

```sql
drop index if exists document_chunks_embedding_hnsw_idx;
create index document_chunks_embedding_hnsw_idx
  on public.document_chunks
  using hnsw (embedding extensions.vector_cosine_ops);
```
