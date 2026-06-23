# GreenGag Backend

FastAPI multi-agent audit API. Python package: `greengag`.

## Structure

```
backend/
├── greengag/
│   ├── main.py              # FastAPI app
│   ├── config.py            # env validation
│   ├── api/routes/          # health, audit SSE, documents ingest/extract
│   ├── agents/              # Report Parser, Ledger, Media, Geospatial, Orchestrator
│   ├── providers/           # OpenAI embeddings, Supabase store
│   ├── services/            # PDF chunker, RAG retriever, Claude extractor, pipelines
│   ├── models/schemas.py    # AuditPayload contract (mirrors frontend types)
│   ├── mocks/fixtures.py    # deterministic demo data
│   └── scoring/integrity.py # Weighted Integrity Index (deterministic)
├── supabase/                # schema.sql + reset.sql for pgvector RAG
├── requirements.txt
└── README.md
```

## Run

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill Supabase + OpenAI + Anthropic for live pipeline
uvicorn greengag.main:app --reload --port 8000
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health + config probe |
| POST | `/api/audit` | Start orchestrated audit |
| GET | `/api/audit/stream` | SSE agent updates |
| POST | `/api/documents/ingest` | Upload PDF → chunk → embed → Supabase |
| POST | `/api/documents/{id}/extract` | RAG retrieve → Claude extract → claims |
| GET | `/api/documents/{id}` | Document status + stored claims |

## Report Parser pipeline (live)

1. **Ingest** — PDF uploaded to Supabase Storage; page-aware chunks with `pillar_hint`; OpenAI `text-embedding-3-large` at `dimensions=2000`; vectors stored in `document_chunks`.
2. **Extract** — Per-pillar fixed queries → top-8 vector search → hybrid `pillar_hint` boost → 0.55 threshold → 15–20 chunks to Claude with taxonomy prompt → Pydantic validate + 1 retry → claims persisted.

Requires: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `backend/supabase/schema.sql` applied in Supabase.

Without pipeline keys, document endpoints return mock fixture data (same as frontend demo).
