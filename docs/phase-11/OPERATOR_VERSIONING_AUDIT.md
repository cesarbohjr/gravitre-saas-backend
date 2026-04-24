# Phase 11 — Operator Versioning Audit

## Scope
Assess existing support for immutable operator versioning and activation per environment.

## Capabilities Already Implemented
- Operators table with admin-managed definitions.
- Operator sessions and action plans with execution safety controls.
- Org and environment scoping via auth + `X-Environment`.
- Approval and policy enforcement via workflow execution.

## Capabilities Missing
- Immutable operator versions.
- Version listing and creation endpoints.
- Active version pointer per environment.
- Recording operator_version_id on sessions, plans, actions.
- UI for version list, create/activate controls.

## Relevant Files
- `backend/app/operators/router.py`
- `backend/app/operators/repository.py`
- `backend/app/operators/schemas.py`
- `supabase/migrations/20260312000001_phase10_operators.sql`
- `apps/web/app/agents/page.tsx`
- `apps/web/app/agents/[id]/page.tsx`
- `apps/web/lib/operators-api.ts`

## Conclusion
Operator versioning is not implemented. Proceed to architecture plan and implementation.
