# Phase 11 — Operator Versioning Plan

## Goals
Add immutable operator versions with per-environment activation, and record the operator_version_id used for sessions, action plans, and actions.

## Minimal Backend Changes

### Tables
- `operator_versions`
  - Immutable snapshots of operator definition and connector bindings.
- `operator_active_versions`
  - Per-environment active version pointer.
- Add `operator_version_id` to:
  - `operator_sessions`
  - `operator_action_plans`
  - `operator_actions`

### Endpoints
- `POST /api/v1/operators/{id}/versions`
- `GET /api/v1/operators/{id}/versions`
- `POST /api/v1/operators/{id}/versions/{version_id}/activate`
- `GET /api/v1/operators/{id}/active` (optional; can be derived in list/detail responses)

### Resolution Rules
- Session creation resolves active version for the requested environment.
- Action plan creation uses session.operator_version_id.
- Action execution uses plan.operator_version_id (for audit linkage).

## Minimal Frontend Changes
- `/agents` list shows active version per operator (for current environment).
- `/agents/[id]` shows version list and admin controls:
  - Create version
  - Activate version
- Non-admins can view versions but cannot modify.

## Security
- Org scoping from auth only.
- Environment scoping from `X-Environment`.
- No changes to connector execution policy.
- No auto-execution.

## Known Limitations
- Versioning is environment-specific; separate versions can be active per environment.
- Operator version content is immutable after creation.
