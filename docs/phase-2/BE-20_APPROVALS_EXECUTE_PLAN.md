# BE-20 — Approvals + Constrained Execute Plan (Option C)

**Authority:** SYSTEM.md → docs/MASTER_PHASED_MODULE_PLAN.md, BE-11 (workflow_defs, workflow_runs, workflow_steps, audit_events), BE-12 (audit query).  
**Phase:** 2 — Assisted Execution  
**Scope:** Per-workflow approval gate and constrained execute mode. Option C: approvals configurable per workflow with org default.  
**Status:** Planning only — no code.  
**Dependencies:** BE-00 (auth, org context), BE-11, BE-12.

---

## 1. Approval Model (Option C — Per-Workflow with Org Default)

### 1.1 approval_policies (new table)

| Column | Type | Constraints |
|--------|------|-------------|
| id | uuid | PK, default gen_random_uuid() |
| org_id | uuid | NOT NULL, FK → organizations(id) ON DELETE CASCADE |
| workflow_id | uuid | NULLABLE, FK → workflow_defs(id) ON DELETE CASCADE. **NULL = org default policy** |
| run_types | text[] | NOT NULL, e.g. `['execute']` — which run_types this policy applies to |
| required_approvals | int | NOT NULL, default 1 |
| approver_roles | text[] | NOT NULL, subset of `{admin, member}` — only these roles may approve |
| created_at | timestamptz | NOT NULL, default now() |
| updated_at | timestamptz | NOT NULL, default now() |
| created_by | uuid | optional, FK → auth.users(id) ON DELETE SET NULL |

- **Constraint:** `UNIQUE (org_id, workflow_id)` — at most one policy per org per workflow. `workflow_id IS NULL` → org default.
- **Semantics:**
  - `workflow_id IS NULL` → org default policy; applies when no workflow-specific policy exists.
  - `workflow_id` set → overrides org default for that workflow only.
- **Index:** `(org_id)`, `(org_id, workflow_id)`.
- **RLS:** org-scoped; SELECT by backend. No policy CRUD API in BE-20 (manual seed or later module).

### 1.2 Policy Resolution Algorithm (explicit)

**Input:** `org_id`, `workflow_id`, `run_type` (e.g. `execute`).

**Steps:**

1. **Workflow-specific:** Look up policy where `org_id = ? AND workflow_id = ? AND run_type = ANY(run_types)`. If found → use it.
2. **Org default:** Else look up policy where `org_id = ? AND workflow_id IS NULL AND run_type = ANY(run_types)`. If found → use it.
3. **BE-20 safe default:** Else use hardcoded default:
   - `required_approvals = 1`
   - `approver_roles = ['admin']`
   - Policy applies to `run_type = execute`.

**Output:** Resolved `(required_approvals, approver_roles)`.

### 1.3 run_approvals (new table)

| Column | Type | Constraints |
|--------|------|-------------|
| id | uuid | PK, default gen_random_uuid() |
| run_id | uuid | NOT NULL, FK → workflow_runs(id) ON DELETE CASCADE |
| org_id | uuid | NOT NULL, FK → organizations(id) ON DELETE CASCADE |
| approver_id | uuid | NOT NULL, FK → auth.users(id) ON DELETE CASCADE |
| status | text | NOT NULL, CHECK IN ('approved', 'rejected') |
| comment | text | optional |
| created_at | timestamptz | NOT NULL, default now() |

- **Unique:** `(run_id, approver_id)` — one decision per approver per run.
- **Index:** `(run_id)`, `(org_id)`.
- **Immutable:** No updates after insert (audit trail).

### 1.4 workflow_runs extension (existing table)

Add columns:

| Column | Type | Constraints |
|--------|------|-------------|
| approval_status | text | optional: `pending_approval` \| `approved` \| `rejected` |
| required_approvals | int | optional, cached from resolved policy at run creation |
| status | — | extend CHECK to include `pending_approval` |

- `status = pending_approval` when approvals required and not yet met.
- `approval_status` tracks approval state; `required_approvals` stored for display.

---

## 2. Role Model (Minimal Closed Set)

### 2.1 Allowed roles (BE-20)

- **admin** — May approve/reject when in `approver_roles`. Full execute visibility.
- **member** — May create execute runs. May approve only if `member` is in `approver_roles` for that policy. View runs in org.
- **viewer** (optional) — Read-only; cannot execute or approve. Include only if `organization_members.role` already supports it.

**Closed set:** `{admin, member}`. `approver_roles` in policies must reference only these values.

### 2.2 Stop condition

If `organization_members.role` contains values outside this set, or role column is missing/inconsistent, **BE-20 must STOP** and require resolution before implementation.

---

## 3. Execution Invariants (Non-Negotiable)

1. **org_id from auth only** — Never from request body.
2. **definition_snapshot + parameters frozen at run creation** — Immutable for run lifetime. No edits.
3. **run_hash immutable** — Stored at creation; never updated.
4. **Approval decisions immutable after run starts** — Once run transitions to `running`, no changes to `run_approvals` or `approval_status` for that run.
5. **Audit events for:** `created`, `pending_approval`, `approval_recorded`, `approved`, `rejected`, `started`, `step_started`, `step_completed`, `step_failed`, `completed`, `failed`, `cancelled`.
6. **No "promote dry-run to execute"** — Explicitly out of scope for BE-20. Execute is created only via `POST /api/workflows/execute` with `workflow_id`. No `dry_run_id` parameter. Dry-run and execute are separate run records.

---

## 4. Concurrency Policy (Decided: Option B)

**Rule:** Deny concurrent execute runs **per workflow**. At most one `run_type = execute` run with `status IN ('running', 'pending_approval')` per `workflow_id` per org.

**HTTP behavior:**

- On `POST /api/workflows/execute`: Before creating a new run, check for existing run with `workflow_id = ?`, `org_id = ?`, `run_type = 'execute'`, `status IN ('running', 'pending_approval')`.
- If such a run exists → **409 Conflict**, body: `{ "detail": "Workflow already has an active run", "active_run_id": "<uuid>" }`.
- Else → create run and proceed.

**Alternatives not chosen:**

- A) Allow concurrent executes — rejected (risk of duplicate work).
- C) Per-org concurrency — rejected (too restrictive; different workflows can run in parallel).

---

## 5. Execute Semantics

### 5.1 run_type = execute

- Uses `workflow_runs`, `workflow_steps`, `audit_events` (existing).
- `run_type = 'execute'`; status extends to `pending_approval`.

### 5.2 Run state machine

```
pending_approval ──(approve, threshold met)──> running ──> completed | failed
       │                    │
       └──(reject)──────────┴────────────────────────────────────────> cancelled
```

### 5.3 Step state machine

```
pending → running → completed | failed | skipped
```

- Sequential by `step_index`. On step failure: run → `failed`, subsequent steps → `skipped`.

### 5.4 Step types: allowed vs disallowed (BE-20)

| Type | Execute allowed? | Notes |
|------|------------------|-------|
| `rag_retrieve` | **Yes** | Read-only; same as dry-run. |
| `noop` | **Yes** | No-op. |
| `transform` | **No** | Dry-run may simulate; execute cannot run. 400 at create. |
| `condition` | **No** | Dry-run may simulate; execute cannot run. 400 at create. |
| External (HTTP, webhook, etc.) | **No** | Forbidden in Phase 2. |

- Only `rag_retrieve` and `noop` permitted. Any other step type in definition → **400** at execute creation.

---

## 6. API Contracts

### 6.1 POST /api/workflows/execute

- **Auth:** Required. Org from auth only.
- **Request body:** `{ workflow_id: uuid (required), parameters?: object }`
- **Behavior:**
  1. Resolve approval policy (workflow-specific → org default → BE-20 safe default).
  2. **Concurrency:** If active execute run exists for workflow → **409 Conflict**.
  3. Load workflow; validate only `rag_retrieve` and `noop` steps → else **400**.
  4. Validate parameters (size limits per BE-11).
  5. Create run: `run_type = execute`, `definition_snapshot`, `parameters`, `run_hash`, `required_approvals` (from policy).
  6. If `required_approvals = 0` → `status = running`, create steps, start execution, emit `created` + `started`.
  7. Else → `status = pending_approval`, `approval_status = pending_approval`, create steps (all `pending`), emit `created` + `pending_approval`.
- **Response (201):**
  - `{ run_id, status, approval_status?, approval_required, required_approvals, approvals_received, message? }`
  - `approval_required = true` when `required_approvals > 0`.
  - `approvals_received` = count of approved rows in `run_approvals` (0 at creation).
- **Status codes:** 400 (invalid def/params), 401/403 (auth), 404 (workflow not found), **409** (active run exists).

### 6.2 POST /api/workflows/runs/:id/approve

- **Auth:** Required. Caller role must be in resolved policy's `approver_roles`.
- **Request body:** `{ comment?: string }`
- **Behavior:**
  1. Load run; validate org, `run_type = execute`, `status = pending_approval`.
  2. Resolve policy for run's workflow; verify caller role in `approver_roles`.
  3. Insert `run_approvals` (status = approved); if `(run_id, approver_id)` exists → **400** (already approved).
  4. Count distinct approvers with status = approved. If >= `required_approvals` → set `approval_status = approved`, `status = running`; start execution; emit `approved`, `started`.
  5. Else emit `approval_recorded`.
- **Response (200):** `{ run_id, status, approval_status, required_approvals, approvals_received, message }`
- **Status codes:** 400 (not pending / already approved), 403 (not approver), 404.

### 6.3 POST /api/workflows/runs/:id/reject

- **Auth:** Required. Caller role must be in `approver_roles`.
- **Request body:** `{ comment?: string }`
- **Behavior:** Insert `run_approvals` (status = rejected); set run `approval_status = rejected`, `status = cancelled`; emit `rejected`.
- **Response (200):** `{ run_id, status, approval_status, message }`
- **Status codes:** 400 (not pending), 403 (not approver), 404.

### 6.4 GET /api/workflows/runs/:id (extended)

- **Auth:** Required. Org-scoped.
- **Response (200):** Existing run + steps, plus:
  - `approval_required` (bool) — `required_approvals > 0` at creation.
  - `approval_status` — `pending_approval` | `approved` | `rejected` | null.
  - `required_approvals` — from run row.
  - `approvals_received` — count of `run_approvals` where status = approved.

---

## 7. Security

### 7.1 Org scoping from auth only

- All endpoints derive `org_id` from BE-00 `get_org_context`. No client-supplied org for auth.

### 7.2 Service role constraints

- Backend uses service role for writes. Never trust client `org_id`, `approver_id`, or role. All from JWT + DB.

### 7.3 Audit actions (complete list)

| Action | When |
|--------|------|
| `workflow.execute.created` | Run created |
| `workflow.execute.pending_approval` | Run requires approval |
| `workflow.execute.approval_recorded` | Approve called, threshold not met |
| `workflow.execute.approved` | Threshold met |
| `workflow.execute.rejected` | Reject called |
| `workflow.execute.started` | Execution begins |
| `workflow.execute.step_started` | Step begins |
| `workflow.execute.step_completed` | Step completes |
| `workflow.execute.step_failed` | Step fails |
| `workflow.execute.completed` | Run completes |
| `workflow.execute.failed` | Run fails |
| `workflow.execute.cancelled` | Run cancelled |

- Metadata: no PII, no query text, no embeddings. Structural fields only (run_type, workflow_id, step_index, step_id, error_code).

---

## 8. Stop Conditions

**Implementation must STOP and ask if:**

1. **Role model absent:** `organization_members.role` missing or contains values outside `{admin, member}`.
2. **Policy resolution ambiguity:** Behavior when multiple policy rows could match (should not occur with UNIQUE; verify).
3. **External actions requested:** Any HTTP/webhook/external step type — reject.
4. **Promote dry-run to execute requested:** Explicitly out of scope; reject.
5. **Conflict with SYSTEM.md or MASTER plan:** Any scheduler, agents, or cross-org expansion — halt.

---

## 9. Non-Goals

- No UI (FE-20 separate).
- No external actions, scheduler, or agents.
- No RBAC beyond `admin` | `member`.
- No policy CRUD API in BE-20.
- No "promote dry-run to execute."

---

## 10. Implementation Notes (BE-20 Complete)

**Migration:** `supabase/migrations/20250204000006_be20_approvals_execute.sql`

- `approval_policies`: run_types text[], workflow_id nullable for org default
- `run_approvals`: UNIQUE(run_id, approver_id)
- `workflow_runs`: approval_status, required_approvals, approver_roles; status includes pending_approval, cancelled

**Backend:**

- `backend/app/workflows/policy.py`: resolve_policy (workflow → org default → safe default), get_user_role, check_concurrency, validate_execute_steps
- `backend/app/workflows/execute.py`: execute_workflow_steps (rag_retrieve + noop only); steps_exist=True for approval flow
- `backend/app/workflows/repository.py`: create_execute_run, insert_run_approval, get_approval_counts; emit_execute_* audit helpers
- `backend/app/routers/workflows.py`: POST /api/workflows/execute, POST /api/workflows/runs/:id/approve, POST /api/workflows/runs/:id/reject; GET runs/:id extended with approval_required, approval_status, required_approvals, approvals_received, approver_roles

**Policy resolution:** `.is_("workflow_id", None)` for org default. run_types checked for `execute` in array.

**Approval logic:** Any rejection cancels run. Idempotent approve (return 200 if already approved). Reject returns 400 if caller already approved.

**Concurrency:** 409 with `{detail, active_run_id}` when active execute run exists for same (org_id, workflow_id).

**Approval floor:** If any step type is `slack_post_message`, `email_send`, or `webhook_post`, required_approvals is forced to `>= 1` at execute creation, regardless of policy. Audit: `policy.override.approval_floor_applied`.
