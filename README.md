# GreenGag — Greenwashing Audit Console

Multi-agent platform that audits corporate ESG claims by cross-referencing PDF reports, financial ledgers, media, and geospatial data, then surfaces a weighted fraud-risk score for compliance reviewers.

This build is **mock-first**: the full wizard (Upload → Claims → Evidence → Dashboard) runs without API keys. The **Report Parser** ingest/extract pipeline can run live when Supabase + OpenAI are configured.

---

## Quick start (local dev)

Use **two terminals** from the project root `GreenGag/`.

### Terminal 1 — Backend (port 8000)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example ..\.env
uvicorn main:app --reload --port 8000
```

macOS / Linux:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn main:app --reload --port 8000
```

Sanity check: open [http://localhost:8000/api/health](http://localhost:8000/api/health) — expect `"status": "ok"`.

### Terminal 2 — Frontend (port 5173)

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` → `http://localhost:8000`.

---

## Demo workflow (no keys required)

1. **Upload** — click **Load sample report** (uses mock document + fixture claims).
2. **Claims** — review extracted claims; after extraction finishes, **Generate extraction report** appears (PDF needs WeasyPrint on Windows — see backend README).
3. **Evidence** — select a claim → **Triangulate evidence** to run the agent cascade (SSE).
4. **Dashboard** — weighted integrity index and executive summary.

Without Supabase/OpenAI keys, document endpoints return the same deterministic mock data as the frontend fixtures.

---

## Project layout

| Path | Role |
|------|------|
| `backend/` | FastAPI app — run `uvicorn main:app` from here |
| `backend/agents/report_parser/` | PDF ingest, RAG extract, report PDF |
| `backend/models/schemas.py` | `AuditPayload` contract (mirrors frontend types) |
| `backend/supabase/` | SQL schema for live RAG (pgvector) |
| `frontend/src/` | React wizard + audit surfaces |
| `.env.example` | Copy to `.env` at **repo root** |

---

## Configuration

Copy `.env.example` → `.env` at the **repository root** (not inside `backend/`).

| Variable | Purpose |
|----------|---------|
| `GREENGAG_DATA_MODE` | `mock` (default) or `live` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY` | Live Report Parser pipeline |
| Other keys | Full live audit agents (ledger, media, geo) — mostly stubbed |

**Mock mode** — no keys required; agents and document API use `backend/mocks/fixtures.py`.

**Live Report Parser** — set the three pipeline keys above and apply `backend/supabase/schema.sql` in Supabase. See [backend/supabase/README.md](backend/supabase/README.md).

**Live audit (`GREENGAG_DATA_MODE=live`)** — requires all keys in `.env.example`; several agents still raise `NotImplementedError` for external integrations.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'greengag'` | Old entrypoint — use `uvicorn main:app` from `backend/`, not `greengag.main:app`. |
| Frontend loads but upload/extract fails | Start backend on `:8000`; check [http://localhost:8000/api/health](http://localhost:8000/api/health). |
| Report PDF returns 503 | Install WeasyPrint native libs (Windows: MSYS2) — [backend README](backend/README.md). |
| Live ingest fails | Apply Supabase schema; verify `SUPABASE_*` and `OPENAI_API_KEY` in root `.env`. |
| `.venv\Scripts\activate` not found | Use `.venv` not `venv`; create with `python -m venv .venv` inside `backend/`. |

---

## API overview

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health + data mode |
| POST | `/api/audit` | Start orchestrated audit |
| GET | `/api/audit/stream` | SSE agent updates |
| POST | `/api/documents/ingest` | Upload PDF |
| POST | `/api/documents/{id}/extract` | RAG + LLM claim extraction |
| POST | `/api/documents/{id}/report/pdf` | Extraction report PDF |
| GET | `/api/documents/{id}` | Document status + claims |

Full backend notes: [backend/README.md](backend/README.md).

---

## Data contract

Backend `models/schemas.py::AuditPayload` and frontend `src/types/audit.ts::AuditPayload` stay in lockstep. The SSE stream deserializes directly into React state.

```
AuditPayload
├── meta              target_entity, project_name, coordinates
├── agent_states      per-agent status, risk, rationale_trail
├── discrepancies     claim ↔ evidence linkages
└── global_metrics    weighted_risk_score, verdict, summary
```

Geospatial agent carries **50%** of the Weighted Integrity Index and holds veto power.
