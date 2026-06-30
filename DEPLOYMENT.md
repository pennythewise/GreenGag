# Docker & Railway Deployment

## Local Docker Run

Build and run the frontend and backend:

```bash
docker compose up --build
```

Open the app at `http://localhost:5173`. The frontend container proxies `/api/*`
to the backend container.

Run the optional local pgvector database:

```bash
docker compose --profile database up --build
```

The local database loads `backend/supabase/schema.sql` on first startup. This is
mainly for schema testing because the backend currently uses Supabase through
`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, not a direct Postgres connection.

## Railway

Recommended Railway setup:

1. Create a Railway service for `backend/`.
   - Root directory: `backend`
   - Dockerfile path: `backend/Dockerfile`
   - Railway provides `PORT`; the container command already uses it.
   - Set backend variables from `.env.example`, especially:
     - `GREENGAG_DATA_MODE`
     - `OPENAI_API_KEY`
     - `OPENROUTER_API_KEY`
     - `OPENROUTER_MODEL`
     - `OPENROUTER_BASE_URL`
     - `SUPABASE_URL`
     - `SUPABASE_SERVICE_ROLE_KEY`

2. Create a Railway service for `frontend/`.
   - Root directory: `frontend`
   - Dockerfile path: `frontend/Dockerfile`
   - Set `BACKEND_URL` to the backend service URL, for example:
     `https://your-backend.up.railway.app`
   - The browser calls `/api/*` on the frontend domain; Nginx forwards it to
     `BACKEND_URL`.

3. Database choice:
   - Use the existing Supabase project for document storage and vector search.
   - Only add Railway Postgres if you plan to migrate away from Supabase APIs.
     The app does not currently read `DATABASE_URL` directly.

## Useful Checks

```bash
docker compose config
docker compose build backend
docker compose build frontend
```
