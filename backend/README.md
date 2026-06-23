# GreenGag Backend

FastAPI multi-agent audit API. Python package: `greengag`.

## Structure

```
backend/
├── greengag/
│   ├── main.py              # FastAPI app
│   ├── config.py            # env validation
│   ├── api/routes/          # HTTP handlers (health, audit, SSE)
│   ├── agents/              # Report Parser, Ledger, Media, Geospatial, Orchestrator
│   ├── models/schemas.py    # AuditPayload contract (mirrors frontend types)
│   ├── mocks/fixtures.py    # deterministic demo data
│   └── scoring/integrity.py # Weighted Integrity Index (deterministic)
├── requirements.txt
└── README.md
```

## Run

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env   # optional in mock mode
uvicorn greengag.main:app --reload --port 8000
```

Endpoints:
- `GET /api/health`
- `POST /api/audit`
- `GET /api/audit/stream` (SSE)
