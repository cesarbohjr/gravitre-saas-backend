# P8-1: Workflow Versioning

## Architecture
- Immutable workflow versions stored separately from `workflow_defs`.
- Active version pointer per org + environment + workflow.
- Runs snapshot the active version definition and version id.

## Endpoints
- `POST /api/v1/workflows/:id/versions`
  - Creates a version from the stored workflow definition.
- `GET /api/v1/workflows/:id/versions`
  - Lists versions (id, version, created_at, created_by, schema_version).
- `POST /api/v1/workflows/:id/versions/:version_id/activate`
  - Sets active version pointer.
- `GET /api/v1/workflows/:id/active`
  - Returns active version + definition.

## Data Model
- `workflow_versions`
  - `org_id`, `environment`, `workflow_id`, `version`, `definition`, `schema_version`
- `workflow_active_versions`
  - `org_id`, `environment`, `workflow_id`, `active_version_id`
- `workflow_runs`
  - `workflow_version_id` (nullable), plus existing `definition_snapshot`

## Org + Environment Scoping
- All version queries are scoped by `org_id`, `environment`, and `workflow_id`.
- Environment is derived from `X-Environment` header.

## Audit Events
- `workflow.version.created`
- `workflow.version.activated`

## Stop Conditions
- No active version when executing or dry-running with workflow_id → `409`.
- Missing workflow → `404`.
- Non-admin role → `403`.

## Non-Goals
- Editing workflow definitions via version endpoints.
- Creating versions from arbitrary payloads.
