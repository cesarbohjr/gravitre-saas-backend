# P8-2: Environment Promotion

## Architecture
- Promote a source version in the current environment to a new immutable version in a target environment.
- Promotion does not auto-activate by default.

## Endpoint
- `POST /api/v1/workflows/:id/versions/:version_id/promote`
  - Body: `{ "to_environment": "staging" | "production" }`
  - Admin-only.

## Data Model
- Creates a new row in `workflow_versions` scoped to target `environment`.
- Version number increments per `(org_id, environment, workflow_id)`.

## Org + Environment Scoping
- Source version lookup uses `org_id`, `environment` (current header), and `workflow_id`.
- Target version uses `org_id`, target environment, and `workflow_id`.

## Audit Events
- `workflow.version.promoted` (includes from_env, to_env, source_version_id, target_version_id)

## Stop Conditions
- Invalid or same target environment → `400`.
- Missing source version → `404`.
- Non-admin role → `403`.

## Non-Goals
- Cross-org promotion.
- Auto-activation in target environment.
