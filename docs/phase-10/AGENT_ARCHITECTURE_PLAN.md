# Phase 10 — Agent Architecture Plan (Minimal Additions)

## Goals
Add enterprise AI Operators (Agents) with minimal new architecture while reusing existing workflows, approvals, policy engine, connectors, and context packs.

## Backend Changes

### New Tables
- `operators`
  - Stores operator definition, prompts, deployment status, and guardrails.
- `operator_connector_bindings`
  - Many-to-many mapping of operators to allowed connectors.
- `operator_sessions`
  - Tracks employee usage sessions with environment and status.
- `operator_action_plans`
  - Stores generated action plans with explainability and guardrail snapshots.
- `operator_actions`
  - Tracks execution requests and ties to workflow runs.

### New Services/Modules
- `backend/app/operators/`
  - `router.py` — API endpoints under `/api/operators`
  - `schemas.py` — request/response models
  - `repository.py` — Supabase CRUD helpers
  - `services/plans.py` — build and persist operator action plans
  - `services/execution.py` — confirm + execute via workflows (no auto-exec)

### API Endpoints
- `GET /api/v1/operators`
- `POST /api/v1/operators` (admin)
- `GET /api/v1/operators/{id}`
- `PATCH /api/v1/operators/{id}` (admin)
- `GET /api/v1/operators/{id}/sessions`
- `POST /api/v1/operators/{id}/sessions`
- `GET /api/v1/operators/sessions/{id}`
- `POST /api/v1/operators/{id}/action-plans`
- `POST /api/v1/operators/{id}/run` (confirm required)

### Execution Flow
1. Employee creates operator session.
2. Context packs are loaded (existing endpoints).
3. Action plan generated and stored.
4. User confirms a step marked executable.
5. Operator executes via workflow execution APIs.
6. Result recorded in `operator_actions` with link to workflow run.
7. Audit event written for operator action.

### Security Rules
- `org_id` always derived from auth.
- `X-Environment` always required and stored.
- Operator execution requires explicit confirmation.
- Operator execution reuses workflow approvals and policy engine.
- Connector secrets remain write-only.

## Frontend Changes

### Pages
- `/agents`
  - List operators and create new (admin).
- `/agents/[id]`
  - Operator detail with prompt, guardrails, connectors, environment scope.
- `/operator`
  - Operator selector, session controls, task input, action plan display, execution history.

### Components
- `OperatorSelector`
- `OperatorSessionView`
- `OperatorTaskInput`
- `ActionPlanCard` (reusing ActionPlan + ActionProposalCard where possible)
- `OperatorExecutionHistory`

### Client APIs
- `apps/web/lib/operators-api.ts`
  - CRUD operators, sessions, action plans, execution.

## Database Tables (Fields Summary)

### operators
- `id`, `org_id`, `name`, `description`, `status`
- `system_prompt`
- `allowed_environments` (text[])
- `requires_admin`, `requires_approval`, `approval_roles`
- `created_by`, `created_at`, `updated_at`

### operator_connector_bindings
- `id`, `org_id`, `operator_id`, `connector_id`, `created_at`

### operator_sessions
- `id`, `org_id`, `operator_id`, `environment`
- `title`, `status`, `current_task`
- `created_by`, `created_at`, `updated_at`

### operator_action_plans
- `id`, `org_id`, `operator_id`, `session_id`, `environment`
- `title`, `summary`, `prompt`
- `primary_context`, `related_contexts`
- `steps`, `guardrails`
- `status`, `created_by`, `created_at`, `updated_at`

### operator_actions
- `id`, `org_id`, `operator_id`, `session_id`, `plan_id`
- `step_id`, `action_type`, `status`
- `workflow_run_id`, `created_by`, `created_at`

## Known Limitations (Minimal Plan)
- No LLM integration; action plans remain deterministic.
- Direct connector execution is not added; operators execute via workflows.
- Operator versioning deferred (single operator definition per ID).
