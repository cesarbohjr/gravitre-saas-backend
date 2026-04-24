# Phase 10 — Agent Capability Audit

## Scope
Assess existing AI Operator / Agent capabilities across admin, employee, integration, and lifecycle needs.

## Capabilities Already Implemented

### Operator Console Foundations
- Operator console route and layout (`/operator`) with sessions list, workspace, context panel, and guardrails UI.
- Action plan UI components with explainability badges and confirmation UI.
- Context pack UI for runs, workflows, connectors, and sources.

### Operator Context + Action Planning (Backend)
- Context pack endpoints for run, workflow, connector, and source.
- Deterministic action-plan generator with explainability payload.
- Guardrail summary included in action plan response.
- Org scoping via auth-derived `org_id`.
- Environment scoping via `X-Environment`.

### Platform Foundations (Reusable)
- Workflows + workflow versioning + execute flow.
- Approval system and approval policies.
- Policy engine and workflow policy resolution.
- Connectors with secrets write-only.
- RAG ingestion sources and documents.
- Audit events and query API.

## Capabilities Partially Implemented

### Operator Sessions
- UI has session list and session cards, but sessions are static and not persisted.
- No backend session model or APIs for session create/list/detail.

### Action Plans
- Action plan generation exists, but plans are not stored or associated with sessions/operators.
- No execution records for plan steps.
- No operator-specific policies applied.

### Agent Selection
- `/agents` page exists but is "Coming soon."
- No operator registry or selection data.

## Missing Capabilities

### Admin Capabilities
- Create/edit AI Operators (Agents).
- Store operator system prompts and instructions.
- Attach connectors to operators.
- Restrict operators to environments.
- Define operator-specific approval requirements or guardrails.
- Deploy operators to org (active/inactive status).
- Operator configuration endpoints and tables.

### Employee Capabilities
- Select an operator for a session.
- Provide task/prompt tied to an operator session.
- Attach context packs to an operator session (persisted).
- Action plan creation tied to operator + session + context.
- Execute operator steps with confirmation.
- Operator execution history.

### Enterprise Tool Integration
- Operator execution that triggers workflows.
- Operator execution that relies on connectors (via workflows).
- Operator-driven workflow draft creation or run retries.

### Agent Lifecycle
- Operator definition storage + versioning.
- Operator deployment controls (active/inactive).
- Operator sessions table.
- Operator execution audit records.

## Relevant Files Discovered

### Backend
- `backend/app/operator/router.py`
- `backend/app/operator/schemas.py`
- `backend/app/operator/services/action_plans.py`
- `backend/app/operator/services/context_packs.py`
- `backend/app/workflows/*`
- `backend/app/connectors/*`
- `backend/app/policy/engine.py`
- `backend/app/routers/audit.py`

### Frontend
- `apps/web/app/operator/page.tsx`
- `apps/web/features/operator/*`
- `apps/web/app/agents/page.tsx` (placeholder)
- `apps/web/components/app-shell.tsx`

### Docs
- `docs/phase-8/OPERATOR_UI.md`
- `docs/phase-9/ACTION_PLANS.md`
- `docs/phase-9/CONTEXT_PACKS.md`
- `docs/phase-9/OPERATOR_GUARDRAILS.md`

## Architectural Gaps
- No operator registry or admin CRUD.
- No operator session persistence or audit trail.
- No operator execution endpoints or action history.
- No operator-specific policy/approval configuration.
- No explicit link between operators and connectors/workflows.

## Conclusion
Major operator/agent capabilities are missing. Proceed to Phase 2.
