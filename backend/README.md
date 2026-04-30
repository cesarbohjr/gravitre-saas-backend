# Gravitre Backend (BE-00)

**Authority:** docs/MASTER_PHASED_MODULE_PLAN.md, docs/phase-0/OQ_RESOLUTIONS.md

## Run locally

From repo root (recommended; `.env` at repo root):

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Or from `backend/`:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ensure `.env` has: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`.

AI services layer also expects:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `DEFAULT_FAST_MODEL` (default: `gpt-4o-mini`)
- `DEFAULT_REASONING_MODEL` (default: `claude-3-5-sonnet-20241022`)
- `DEFAULT_EMBEDDING_MODEL` (default: `text-embedding-3-small`)
- `RAG_CHUNK_SIZE` (default: `1000`)
- `RAG_CHUNK_OVERLAP` (default: `200`)
- `RAG_TOP_K` (default: `8`)

## Endpoints

- `GET /health` — no auth; returns `{ status, timestamp }`
- `GET /api/auth/me` — requires `Authorization: Bearer <Supabase JWT>`; returns `{ user_id, org_id?, email? }`

## Acceptance criteria (BE-00)

- [ ] `/health` returns 200 without auth
- [ ] `/api/auth/me` returns 401 without valid JWT
- [ ] `/api/auth/me` returns user/org with valid JWT
- [ ] Logs include request_id and user context
