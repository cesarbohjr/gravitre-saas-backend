# Phase 8: Platform Productization

## Repository Findings
- Backend workflow endpoints live in `backend/app/routers/workflows.py` under `/api/workflows`.
- Approval actions already exist: `/api/workflows/runs/:id/approve` and `/reject`.
- Connectors endpoints exist under `/api/connectors` and are admin-only.
- Environment scoping uses `X-Environment` via `get_environment_context`.
- API versioning uses middleware that rewrites `/api/v1/*` to `/api/*`.
- Frontend workflows UI lives in `apps/web/app/workflows/*`.
- Frontend runs UI lives in `apps/web/app/runs/[id]`.
- Next.js API proxy routes live in `apps/web/app/api/*`.

## Scope
1. Workflow Versioning (immutable versions + active pointer)
2. Environment Promotion (version copy across environments)
3. Connector Management UI (admin-only, write-only secrets)
4. Approvals + Execution Control UI (pending approvals + approve/reject)
