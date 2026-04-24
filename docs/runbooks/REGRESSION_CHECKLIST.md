# Regression Checklist — Safety + Tenancy + Approval Gating

**Purpose:** Manual guardrails to prevent regressions in approvals, SSRF safety, admin‑only writes, org scoping, and PII discipline.

---

## Quick Start: Safety Regression

- Run smoke test: `python -m backend.scripts.smoke_test`
  - Optional env: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` for DB invariants
  - File: `backend/scripts/smoke_test.py`
- Run internal alpha preview: `docs/runbooks/INTERNAL_ALPHA_PREVIEW.md`
- Run when:
  - Before preview
  - Before merge
  - After touching workflows/connectors/ingestion/metrics

**Invariants (must not happen):**
- External actions execute without approvals (approval floor)
- Webhook connects by hostname (must pin validated IP)
- Active doc loses chunks after failed ingest (staged swap)
- Secrets/PII appear in logs, metrics, or UI

---

## RB‑00 — Roles & Membership

1. Sign in as **admin**:
   - `GET /api/org/members` returns 200
   - `PATCH /api/org/members/:id` updates role
2. Sign in as **member**:
   - `PATCH /api/org/members/:id` returns 403
3. Verify `organization_members.role` only contains `admin|member`

---

## BE‑20 — Approvals & Execute

1. Create workflow run requiring approval:
   - `POST /api/workflows/execute` returns `status=pending_approval`
2. Ensure **no execute** happens before approval:
   - No steps run; status remains `pending_approval`
3. Approve run:
   - `POST /api/workflows/runs/:id/approve` moves to `running` and completes
4. Reject run:
   - `POST /api/workflows/runs/:id/reject` sets `status=cancelled`

---

## IN‑10 — Slack (Approval‑Gated)

1. Dry‑run includes `slack_post_message`:
   - Returns simulated output, **no send**
2. Execute with approval:
   - Sends message **only after approval**
3. Audit events present:
   - `slack.send.requested/sent/failed`

---

## IN‑11 — Email (Approval‑Gated)

1. Dry‑run `email_send`:
   - Simulated output only (domain + hashes)
2. Execute after approval:
   - SMTP send occurs
3. Audit events present:
   - `email.send.requested/sent/failed`
4. No email address/body in logs or audit metadata

---

## IN‑12 — Webhook (SSRF‑Safe)

1. Dry‑run `webhook_post`:
   - Simulated output only, **no network**
2. Execute after approval:
   - POST only to allowlisted host
   - Redirects NOT followed
3. SSRF safety:
   - `localhost`, `127.0.0.1`, `10.0.0.1` rejected
4. Audit events:
   - `webhook.send.requested/sent/failed`

---

## DC‑00/DC‑10 — Ingestion

1. Non‑admin user:
   - `POST /api/rag/sources` returns 403
   - UI buttons disabled with message
2. Admin user:
   - Create source (type must be in controlled list)
   - Ingest via text or chunks
3. No file uploads or URL fetchers
4. No raw text logged

---

## MT‑00/MT‑10 — Metrics + UI

1. `GET /api/metrics/overview|workflows|rag|connectors` returns 200
2. Responses contain no PII:
   - No emails, query text, message text, payloads, or URLs
3. UI shows loading/empty/error states and no PII

---

## Org Scoping (Global)

1. Attempt cross‑org access:
   - Wrong org returns 404 or 403 (never 200)
2. Verify no request accepts `org_id` in body

---

## Logging / PII

1. Logs contain:
   - request_id, org_id, run_id, status, latency_ms
2. Logs do **not** contain:
   - query text, message text, payloads, emails, tokens, secrets

---

## Phase 6 — Rollups + Workers + Kill Switches

1. Rollups:
  - Run `python -m backend.scripts.rollup_daily --days 1`
   - Set `METRICS_ROLLUP_ENABLED=true` and re-check metrics endpoints
  - Optional purge: `python -m backend.scripts.retention_purge --cutoff-days 180`
2. Background ingestion:
  - `POST /api/rag/ingest` returns `status=queued`
  - Run worker: `python -m backend.scripts.ingest_worker`
   - `GET /api/rag/ingest/:id` reaches `status=completed`
3. Kill switches:
   - `DISABLE_EXECUTE=true` blocks `/api/workflows/execute`
   - `DISABLE_CONNECTORS=true` blocks connector executions
   - `DISABLE_INGESTION=true` blocks `/api/rag/ingest`
