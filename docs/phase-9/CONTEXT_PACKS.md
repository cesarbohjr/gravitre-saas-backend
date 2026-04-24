# Phase 9 — Context Packs

## Goal
Provide operator-facing, structured context for the entity under investigation without exposing secrets or raw PII.

## Endpoints

All endpoints are org-scoped and environment-scoped via `X-Environment`.

- `GET /api/v1/operator/context/run/:id`
- `GET /api/v1/operator/context/workflow/:id`
- `GET /api/v1/operator/context/connector/:id`
- `GET /api/v1/operator/context/source/:id`

### Response contract (summary)

Each response returns:
- `pack`: `{ id, type, title, summary, status, environment, href }`
- Entity summary + safe lists (recent runs, versions, docs, etc.)
- `environment` echo

### Safety constraints

- No secrets returned (connector secrets remain write-only).
- No raw chunk text or document bodies.
- No input/output snapshots from run steps.
- Payloads are concise and capped (recent items are limited).

## Frontend Components

- `ContextPanel`
- `ContextPackCard`
- `ContextSummaryStrip`

## Environment & Org Scoping

- `org_id` is derived from auth context only.
- `X-Environment` is forwarded by the Next.js proxy and enforced on the backend.

## Known limitations

- Related workflow/connector linkage is best-effort and may be incomplete.
- Context packs list relies on existing entity lists (runs may be unavailable if no pending approvals).

