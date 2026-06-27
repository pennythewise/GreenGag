# GreenGag Backend

FastAPI multi-agent audit API. **Always run commands from this directory** (`backend/`).

## Structure

```
backend/
├── main.py                      # FastAPI entry — uvicorn main:app
├── config.py                    # env validation (loads ../.env)
├── api/routes/                  # health, audit SSE, documents
├── agents/
│   ├── orchestrator.py          # LangGraph supervisor
│   └── report_parser/           # ingest/, extract/, report/, store/, prompts/
├── models/schemas.py            # AuditPayload (shared with frontend)
├── mocks/fixtures.py            # deterministic demo data
├── providers/                   # OpenAI embeddings, MiniLM local routing
├── scoring/integrity.py         # Weighted Integrity Index
├── supabase/                    # schema.sql for live RAG
└── requirements.txt
```

## First-time setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example ..\.env
```

Environment file lives at **repo root** (`GreenGag/.env`), not inside `backend/`.

## Run

```powershell
.venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

API base: [http://localhost:8000](http://localhost:8000)  
Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

Pair with the frontend (`npm run dev` in `frontend/`) so `/api` requests proxy correctly.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health + `data_mode` + secret flags |
| POST | `/api/audit` | Start orchestrated audit |
| GET | `/api/audit/stream` | SSE agent updates |
| POST | `/api/documents/ingest` | Upload PDF → chunk → embed |
| POST | `/api/documents/{id}/extract` | RAG → OpenAI → claims |
| POST | `/api/documents/{id}/report/pdf` | Extraction report PDF |
| GET | `/api/documents/{id}` | Status + stored claims |

## Report Parser (live pipeline)

Requires in root `.env`:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `OPENAI_API_KEY`

Plus `backend/supabase/schema.sql` applied in Supabase ([setup guide](supabase/README.md)).

1. **Ingest** — pymupdf4llm layout chunking → OpenAI embeddings (2000-d) → pgvector store. SHA-256 dedup skips re-embedding identical PDFs.
2. **Extract** — MiniLM pillar routing (top 3 chunks per E/S/G, no threshold gate) → per-pillar GPT (`temperature=0`) → regex claim validation → Supabase.

Optional env: `RAG_CHUNKS_PER_PILLAR=3`, `RAG_PILLAR_ROUTING_MODEL=sentence-transformers/all-MiniLM-L6-v2`, `PILLAR_ROUTING_CONFIDENCE=0.7`.

If pipeline keys are missing, document routes return **mock fixture data** (same as the demo UI).

## Extraction report PDF

`POST /api/documents/{id}/report/pdf` renders cover, summary, rule-based insights, and claim cards via **Jinja2 + WeasyPrint**.

### WeasyPrint on Windows

1. Install [MSYS2](https://www.msys2.org/)
2. In MSYS2 shell: `pacman -S mingw-w64-x86_64-pango`
3. Set user env var: `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\mingw64\bin`
4. Restart terminal and uvicorn

Details: [WeasyPrint Windows guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows)

Without native libs the API returns **503**; ingest/extract still work.

## Common errors

| Error | Cause | Fix |
|-------|--------|-----|
| `No module named 'greengag'` | Stale uvicorn target | `uvicorn main:app` from `backend/` |
| `No module named 'main'` | Wrong working directory | `cd backend` before uvicorn |
| Import errors after git pull | Missing deps | `pip install -r requirements.txt` |
| Supabase RPC errors | Schema not applied | Run `supabase/schema.sql` |
