# P8-3: Connector Management UI

## Architecture
- Admin-only connector configuration with write-only secrets.
- Environment scoping enforced via `X-Environment`.

## Endpoints
- `GET /api/v1/connectors`
- `POST /api/v1/connectors`
- `GET /api/v1/connectors/:id`
- `PATCH /api/v1/connectors/:id`
- `POST /api/v1/connectors/:id/secrets` (write-only)

## Data Model
- `connectors` and `connector_secrets` (secrets encrypted, never returned).

## Org + Environment Scoping
- `org_id` derived from auth context.
- Environment from `X-Environment` header; connectors are filtered by environment.

## Security / Secrets
- Secrets are write-only:
  - never returned in API responses
  - never displayed in UI
  - cleared from UI state after submission

## Stop Conditions
- Missing org context → `403`.
- Missing secrets encryption key → `503` on secret writes.
- Non-admin role → `403`.

## Non-Goals
- Reading or masking existing secrets.
- Connector testing from the UI.
