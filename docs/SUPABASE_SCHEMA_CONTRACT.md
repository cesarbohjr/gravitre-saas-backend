# Supabase Schema Contract

This document defines the current database-to-frontend contract for Gravitre, with `snake_case` in Supabase and `camelCase` in frontend payloads.

## Contract Tables

- `organizations` -> org shell + settings for workspace context.
- `users` -> org-scoped user profile/role projection (linked to `auth.users`).
- `agents` -> frontend agent list/create contract.
- `workflows` -> frontend workflow list/detail/builder contract (`nodes`, `edges`, `config`).
- `runs` -> frontend runs timeline and run detail header contract.
- `run_steps` -> run detail step timeline/log contract.
- `approvals` -> frontend approvals queue contract.
- `connected_systems` -> frontend systems/integrations list contract.
- `api_keys` -> API keys list contract (`key_hash` stored, never returned by API).
- `webhooks` -> webhook settings contract.
- `audit_logs` -> org-scoped audit timeline contract.
- `model_settings` -> model selector defaults/settings contract.

## Field Mapping

The API layer maps with:

- `apps/web/lib/supabase/transforms.ts`
  - `snakeToCamel<T>()`
  - `camelToSnake()`

Examples:

- `org_id` -> `orgId`
- `created_at` -> `createdAt`
- `updated_at` -> `updatedAt`
- `workflow_id` -> `workflowId`
- `run_id` -> `runId`
- `requested_at` -> `requestedAt`

## API Routes Using Supabase Directly

- `/api/agents` (GET, POST)
- `/api/workflows` (GET, POST)
- `/api/workflows/[id]` (GET, PUT)
- `/api/runs` (GET)
- `/api/runs/[id]` (GET)
- `/api/approvals` (GET)
- `/api/settings/models` (GET, PATCH)
- `/api/settings/api-keys` (GET, PATCH)
- `/api/settings/webhooks` (GET, PATCH)
- `/api/systems` (GET, POST)
- `/api/systems/[id]` (DELETE)

## Routes Still Backed by FastAPI

Execution/intelligence and privileged operations remain on FastAPI:

- AI execution/RAG/agent execution workflows
- approvals mutation endpoints (`/api/approvals/[id]/approve`, `/api/approvals/[id]/reject`)
- workflow execution controls and job orchestration
- billing and secure webhooks
- connector execution background work

## Existing Schema Conflicts and Safe Path

Existing migrations already include related legacy/backend-first tables:

- `workflow_defs`, `workflow_runs`, `workflow_steps`
- `operators`, `operator_versions`, `operator_sessions`
- `connectors`
- existing `organizations`, `approvals`, `audit_logs`

Safe migration strategy implemented:

- Additive changes only (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).
- No destructive table drops.
- Legacy tables retained for FastAPI compatibility.
- New/updated contract tables coexist with legacy tables during migration period.

## Remaining Mocks

Mocks remain where a direct table/contract path is not fully wired yet:

- settings section UIs still mostly local form state for some actions.
- workflow duplicate/delete in list page still TODO placeholders.
- some non-priority pages continue using fallback datasets.

## Migration Risks

- Dual-table period (`workflows` + `workflow_defs`, `runs` + `workflow_runs`) can drift if write paths are split.
- RLS depends on valid `organization_members` membership for authenticated users.
- Existing production rows may lack newly added fields and rely on defaults.

## Manual Supabase Actions

1. Review and run migration `supabase/migrations/20260424_gravitre_frontend_contract_schema.sql` in target environments.
2. Validate RLS behavior with authenticated users from at least two orgs.
3. Backfill contract tables from legacy tables if historical data parity is required immediately.
4. After parity validation, decide whether to consolidate legacy tables into contract tables.
