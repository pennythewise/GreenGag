# GreenGag — Greenwashing Audit Console

Multi-agent greenwashing detection platform. It audits corporate ESG claims by
cross-referencing unstructured PDF reports against financial ledgers, public
media, and satellite remote-sensing data, then surfaces a weighted fraud risk
score to compliance auditors.

> Product spec: [PRD.md](PRD.md) · Engineering guide: [CLAUDE.md](CLAUDE.md)

This build runs **mock-first**: the full agent graph and dashboard work
end-to-end against deterministic fixtures with no external API keys. Live API
integrations (Sentinel-5P, Planet Labs, NewsAPI, Postgres ledger) drop in behind
the same interfaces — see `GREENGAG_DATA_MODE` below.

---

## What's implemented

**Backend** (`backend/`, FastAPI + async)
- `models/schemas.py` — Pydantic `AuditPayload` contract (single source of truth).
- `config.py` — `os.getenv()` bindings + startup validation (hard-fails in live
  mode on missing keys; warns in mock mode so the demo runs offline).
- `agents/` — 5 async agents (Orchestrator + Report Parser, Ledger Auditor,
  Media Sentinel, Geospatial Truth), each populating a `rationale_trail`.
- `agents/orchestrator.py` — **LangGraph** supervisor applying the Weighted
  Integrity Index (geospatial = 50%) with GeospatialTruthAgent **veto**.
  Falls back to a sequential runner if LangGraph isn't installed.
- `main.py` — `GET /api/health`, `POST /api/audit`, `GET /api/audit/stream` (SSE).

**Frontend** (`frontend/`, React + TypeScript + Vite)
- 7 components: `RiskScoreRing`, `AgentSwimlane`, `PDFViewer`, `LedgerTimeline`,
  `DiscrepancyCanvas`, `MapCanvas`, `SentimentFeed`.
- Design system per CLAUDE.md: eggshell/cream backgrounds, navy/charcoal text,
  sage/slate-blue/terra-cotta accents, 12–16px radii, 150ms fades, cascade
  slide. **No dark theme.**
- XAI lineage: clicking a discrepancy (or a flagged ledger row / PDF claim)
  draws an **animated SVG anchor line** and co-highlights the linked evidence
  across cards.
- Live agent transitions stream from the backend SSE endpoint; if the backend
  is down, the dashboard replays the audit locally from the mock fixture.

---

## Run it

### Backend

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env     # optional; mock mode runs without keys
uvicorn main:app --reload      # http://localhost:8000
```

Sanity check:

```bash
curl localhost:8000/api/health
curl -X POST localhost:8000/api/audit | jq '.global_metrics'
```

### Frontend

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

The Vite dev server proxies `/api` → `http://localhost:8000`, so the dashboard
streams from the live backend automatically. Click **Re-run Audit** to replay
the cascade. With the backend stopped, it falls back to the local mock.

---

## Data modes

`GREENGAG_DATA_MODE` (in `.env`, default `mock`):

- `mock` — agents return deterministic fixtures (`backend/mocks/fixtures.py`,
  mirrored in `frontend/src/mocks/auditPayload.ts`). No external calls.
- `live` — agents call real APIs. Each agent's `_run_live()` is stubbed with the
  exact integration TODO; `config.py` requires all 8 secrets at startup.

Required live keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `PLANET_LABS_API_KEY`,
`SENTINEL_HUB_CLIENT_ID`, `SENTINEL_HUB_CLIENT_SECRET`,
`GOOGLE_EARTH_ENGINE_CREDENTIALS`, `NEWS_API_KEY`, `INTERNAL_LEDGER_DB_URL`.

---

## The contract

Both sides build against one schema. Backend `models/schemas.py::AuditPayload`
and frontend `src/types/audit.ts::AuditPayload` are kept in lockstep — the SSE
stream deserializes straight into the React components.

```
AuditPayload
├── meta            target_entity, project_name, coordinates (GeoJSON Polygon)
├── agent_states    per-agent status / risk_contribution / rationale_trail + findings
├── discrepancies   triangulated claim ↔ evidence linkages (drive the SVG canvas)
└── global_metrics  weighted_risk_score, confidence, verdict, executive_summary
```

## Notes & known gaps

- **MapCanvas** renders the heatmap + claimed-vs-observed time series with
  dependency-free SVG. Swap in Mapbox/Leaflet behind it for live tiles.
- The PRD sample payload uses status `"COMPLETED"` and omits MediaSentinelAgent;
  this build follows the CLAUDE.md enum (`IDLE|PROCESSING|SUCCESS|ALERT`, with
  `SUCCESS` ≙ completed) and includes all 5 agents.
- `agents/*/_run_live()` methods raise `NotImplementedError` with the specific
  integration each needs — the live wiring is the next milestone.
