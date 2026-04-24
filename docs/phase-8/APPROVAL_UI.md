# P8-4: Approvals + Execution Control UI

## Architecture
- Pending approvals list (org + environment scoped).
- Approve/reject actions with admin-only enforcement.
- Execute button in workflow detail; uses active version gating.

## Endpoints
- `GET /api/v1/approvals/pending`
- `POST /api/v1/workflows/runs/:id/approve`
- `POST /api/v1/workflows/runs/:id/reject`
- `POST /api/v1/workflows/execute`

## Data Model
- `workflow_runs` with approval fields (`approval_status`, `required_approvals`)
- `run_approvals` for decisions per approver

## Org + Environment Scoping
- `org_id` from auth context only.
- `X-Environment` used for pending approvals list.

## Audit Events
- Existing BE-20 audit events for approval/execute flows are preserved.

## Stop Conditions
- Non-admin role → `403` for approve/reject.
- No active workflow version when executing → `409`.

## Non-Goals
- Cancel/retry if backend semantics are not supported.
