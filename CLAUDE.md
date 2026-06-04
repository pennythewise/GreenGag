# GreenGag AI Dashboard — Claude Code Guide

> Full product requirements: [PRD.md](PRD.md)

## Project Overview

GreenGag is a high-stakes multi-agent greenwashing detection platform. It audits corporate ESG claims by cross-referencing unstructured PDF reports against financial ledgers, public media, and satellite remote sensing data, then surfaces a weighted fraud risk score to compliance auditors.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI (async) |
| Agent Orchestration | LangGraph |
| LLM | Anthropic Claude (primary), OpenAI (fallback) |
| Frontend | React (component-driven) |
| Maps | Mapbox or Leaflet |
| Database | PostgreSQL |
| Satellite APIs | Sentinel-5P TROPOMI, Planet Labs, Google Earth Engine |
| Scraping/NLP | Custom pipelines + text classification models |

## Project Structure

```
greengag/
├── backend/
│   ├── main.py                  # FastAPI app entrypoint
│   ├── agents/
│   │   ├── orchestrator.py      # OrchestratorAgent — LangGraph supervisor
│   │   ├── report_parser.py     # ReportParserAgent — ESG PDF ingestion
│   │   ├── ledger_auditor.py    # LedgerAuditorAgent — financial cross-check
│   │   ├── media_sentinel.py    # MediaSentinelAgent — news/NGO scraping
│   │   └── geospatial_truth.py  # GeospatialTruthAgent — satellite verification
│   ├── models/
│   │   └── schemas.py           # Pydantic models for the audit state payload
│   └── config.py                # os.getenv() bindings, startup validation
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AgentSwimlane/   # Live multi-agent status cards
│   │   │   ├── DiscrepancyCanvas/ # SVG-linked split viewport
│   │   │   ├── LedgerTimeline/  # Financial audit table
│   │   │   ├── MapCanvas/       # Geospatial heatmap (Mapbox/Leaflet)
│   │   │   ├── PDFViewer/       # Interactive ESG PDF with amber highlights
│   │   │   ├── RiskScoreRing/   # Orchestrator master status ring
│   │   │   └── SentimentFeed/   # Media Sentinel article stream
│   │   └── App.tsx
├── .env.example                 # API key placeholders — never commit .env
└── PRD.md
```

## Core Data Model

The canonical audit state payload (defined in `schemas.py`) is the single source of truth routed between all agents:

```python
class AuditPayload(BaseModel):
    audit_id: str
    meta: AuditMeta           # target_entity, project_name, coordinates (GeoJSON Polygon)
    agent_states: AgentStates # per-agent status, risk_contribution, rationale_trail
    global_metrics: GlobalMetrics  # weighted_risk_score, confidence_score, final_verdict
```

**Weighted Integrity Index:** Geospatial data carries 50% of the final score. GeospatialTruthAgent holds absolute veto power.

## Environment & Secrets

- All secrets loaded via `os.getenv()` — never hardcoded.
- Copy `.env.example` to `.env` to run locally. Never commit `.env`.
- Required keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `PLANET_LABS_API_KEY`, `SENTINEL_HUB_CLIENT_ID`, `SENTINEL_HUB_CLIENT_SECRET`, `GOOGLE_EARTH_ENGINE_CREDENTIALS`, `NEWS_API_KEY`, `INTERNAL_LEDGER_DB_URL`.
- Boot script in `config.py` must validate all keys are present at startup and raise explicit errors for any missing values.

## Agent Implementation Notes

- All agents are async — never use blocking I/O inside agent methods.
- Each agent must populate its `rationale_trail` list with step-by-step reasoning for XAI display.
- Agent `status` must be one of: `IDLE`, `PROCESSING`, `SUCCESS`, `ALERT`.
- `risk_contribution` is a float 0.0–1.0.

## Frontend Notes

- **No dark themes.** Background colors: eggshell white / pale cream. Text: dark navy / slate charcoal. Accents: sage green, slate blue, terra cotta.
- Border radius: 12–16px on all cards and containers.
- State transition animations: 150ms linear fades. Agent stream open animations: horizontal cascade slide.
- SVG connector lines (Discrepancy Canvas, Ledger Timeline) must animate in on click — not static.
- All map overlays use color-coded heatmaps with a side-by-side time-series graph (claimed vs. observed).

## Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env   # then fill in keys
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```
