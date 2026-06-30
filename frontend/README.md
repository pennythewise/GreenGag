# GreenGag Frontend

React + TypeScript + Vite wizard for explainable greenwashing-risk audits.

## Prerequisites

- Node.js 18+
- Backend running at [http://localhost:8000](http://localhost:8000) (see [backend/README.md](../backend/README.md))

## Run

```powershell
cd frontend
npm install
npm run dev
```

App: [http://localhost:5173](http://localhost:5173)

The dev server proxies `/api` → `http://localhost:8000` (see `vite.config.ts`). Start the backend first for live ingest/extract; the UI still renders with local mocks if the API is down.

## Wizard flow

| Step | View | Backend calls |
|------|------|----------------|
| 1 Upload | `UploadView` | `POST /api/documents/ingest` or sample shortcut |
| 2 Claims | `ClaimsView` | `POST /api/documents/{id}/extract`, optional report PDF |
| 3 Evidence | `EvidenceView` | `GET /api/audit/stream` (SSE) |
| 4 Dashboard | `DashboardView` | Uses accumulated audit state |

## Structure

```
frontend/src/
├── app/                 # App shell + wizard routing
├── components/
│   ├── layout/          # Sidebar stepper
│   ├── audit/           # PDF, ledger, map, discrepancy canvas, …
│   └── wizard/          # Step views
├── hooks/useAudit.ts    # SSE stream + mock fallback
├── lib/documents.ts     # ingest / extract / report PDF client
├── types/audit.ts       # AuditPayload (mirrors backend schemas)
└── mocks/auditPayload.ts
```

## Build

```powershell
npm run build
npm run preview
```

Production builds expect the API at the same origin or configure your reverse proxy for `/api`.
