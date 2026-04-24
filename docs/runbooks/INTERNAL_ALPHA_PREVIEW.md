# Internal Alpha Preview Runbook

## Quick Verify (60 Seconds)

1) Backend Health
URL:
http://localhost:8000/health

Expected response:
{ "status": "ok", "timestamp": "<iso>" }

If this fails:
- Backend is not running
- Wrong port
- uvicorn not started
- Environment not bootstrapped

2) Frontend Availability
URL:
http://localhost:3000

Expected result:
- Gravitre UI loads
- No blank screen
- No console fatal errors

If this fails:
- pnpm install not run
- next not installed
- dev script misconfigured

3) Auth Proxy Wiring
URL:
http://localhost:3000/api/auth/me

Expected:
- 401 if not signed in
- 200 with { user_id, org_id? } when signed in

If this fails:
- FASTAPI_BASE_URL not set
- Proxy route misconfigured
- Backend not reachable
- Auth middleware miswired

## Preconditions

1. Supabase running (local or remote)
2. Migrations applied:
   - `20250204000002_create_organizations_and_members.sql`
   - `20250204000003_create_rag_tables.sql`
   - `20250204000004_create_workflow_tables.sql`
   - `20250204000005_audit_query_function.sql`
   - `20250204000006_be20_approvals_execute.sql`
   - `20250204100001_in00_connectors.sql`
   - `20250204100003_dc00_rag_ingest_jobs.sql`
   - `20250204110000_dc00_rag_documents_versioning.sql`
   - `20250220000001_phase6_rollups.sql`
   - `20250220000002_phase6_connector_rate_limits.sql`
   - `20250220000003_phase6_ingest_queue.sql`
   - `20250220000004_phase6_retention.sql`
3. Backend env configured:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_JWT_SECRET`
   - `OPENAI_API_KEY`
4. Frontend env configured:
   - `FASTAPI_BASE_URL`
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`

---

## End‑to‑End Demo Path

### 0) Install prerequisites
- Follow `docs/runbooks/PREREQUISITES.md`

### 1) Bootstrap
- Backend (from repo root):
  - `cd backend`
  - `python -m venv .venv`
  - Windows: `.\.venv\Scripts\activate`
  - macOS/Linux: `source .venv/bin/activate`
  - `python -m pip install --upgrade pip`
  - `pip install -r requirements.txt`
- Frontend (from repo root):
  - `cd apps/web`
  - `pnpm install`

### 2) Start services
- Option A (one command): `pnpm run dev` from repo root
- Option B (two terminals):
  - Backend: `pnpm run dev:backend`
  - Web: `pnpm run dev:web`
- Start ingestion worker (separate terminal, from repo root):
  - `python -m backend.scripts.ingest_worker`
- Verify `GET /health` returns 200
- Run smoke test after backend is up: `python -m backend.scripts.smoke_test`
  - HTTP checks run only if the backend is reachable

### 3) Metrics page loads
Expected:
- `/metrics` loads
- Overview cards show zeros or counts
- No PII displayed

### 4) RAG sources + ingestion
Steps:
- Create source (admin) at `/rag/sources/new`
- Ingest document at `/rag/ingest?source_id=...`
Expected:
- Source created; document list updated
- Ingest returns `status=queued`, then completes once worker runs
- No text logged

### 5) RAG retrieval
Steps:
- Use RAG endpoint or dry‑run workflow with `rag_retrieve`
Expected:
- Retrieval returns chunks with citations
- No query text in logs

### 6) Workflow versioning
Steps:
- Create workflow definition (rag_retrieve + noop)
- Create version and activate it in `/workflows/[id]`
Expected:
- Active version is visible
- Version creation is immutable

### 7) Workflows dry‑run
Steps:
- Run dry‑run in `/workflows/[id]`
Expected:
- Dry‑run created, steps completed
- Audit events present

### 8) Approvals + connectors
Steps:
- Create connector (Slack/Email/Webhook) and secrets
- Create workflow with connector step
- Execute → expect `pending_approval`
- Approve → expect `running` then `completed`
Expected:
- Connector sends only after approval
- Audit events `*.send.*` present
- No message text stored

### 9) Operator demo (Context Pack + Action Plan)
Steps:
- Navigate to `/operator`
- Select a context pack (run/workflow/connector/source)
- Confirm the context summary strip updates
- Review generated action plan with guardrail badges
Expected:
- Environment is visible at all times
- Action plan steps include approvals/admin/execution labels
- Confirmation UI appears for executable actions (no execution occurs)

### 10) Metrics update
Expected:
- Connectors counts increase after sends
- Range switch (7d/30d/90d) works

---

## Expected Outcomes Checklist

- Sources list shows new source
- Ingest job shows completed
- Workflow run shows steps completed
- Approval gate blocks external actions pre‑approval
- Metrics reflect new activity

Common failures and fixes:
- **403 on writes:** ensure admin role
- **503 on ingest:** verify `OPENAI_API_KEY`
- **Connector send failure:** verify connector secrets

---

## Safety Assertions (Must NOT happen)

- External sends without approvals
- Active document losing chunks on failed ingest
- Webhook connecting by hostname instead of pinned IP
- PII displayed in UI or logs
