# GreenGag Frontend

React + TypeScript + Vite wizard dashboard for explainable greenwashing-risk audits.

## Structure

```
frontend/src/
├── app/                 # App shell, routing wizard, entry (main.tsx)
├── components/
│   ├── layout/          # Sidebar stepper
│   ├── audit/           # XAI evidence surfaces (PDF, ledger, map, …)
│   └── wizard/          # Upload → Claims → Evidence → Dashboard steps
├── hooks/               # useAudit (SSE + mock fallback)
├── lib/                 # formatters, selection state, step defs
├── types/audit.ts       # AuditPayload (mirrors backend schemas)
├── mocks/               # offline demo fixture
└── styles/index.css     # design tokens (light theme)
```

## Run

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173 — proxies /api → :8000
```
