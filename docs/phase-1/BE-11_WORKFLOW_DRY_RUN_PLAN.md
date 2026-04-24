# BE-11 — Workflow Dry-Run + Audit Plan (No Side Effects)

**Authority:** SYSTEM.md → docs/MASTER_PHASED_MODULE_PLAN.md  
**Phase:** 1 — Generate & Draft  
**Scope:** Workflow dry-run execution with full auditability; no external side effects  
**Status:** Planning only — no code  
**Dependencies:** BE-00 (auth, org context), BE-10 (RAG retrieval for step integration)

---

## 1. Purpose & Scope

### 1.1 Objective

- Define a **minimal, versioned workflow schema** that can be validated and executed in **dry-run mode**.
- **Dry-run semantics:** Simulate each step; return a **plan + predicted outputs**; **never write outside internal audit/trace tables** (no external APIs, no user data mutation, no side effects beyond recording the run itself).
- **Auditability:** Every dry-run produces a **run record**, **step-level trace records**, and **audit events** so that Phase 2 can enforce an "approvals required" boundary before any real execution.

### 1.2 In Scope (BE-11)

- Workflow definition schema (versioned, JSON structure).
- Dry-run endpoint: validate definition, execute steps in simulation mode, persist run + steps + events.
- Read API for run detail (run + steps + optional event summary).
- Org-scoped access only; org from auth context.

### 1.3 Explicitly Out of Scope (BE-11)

- **No external actions** (no HTTP calls to third parties, no webhooks, no outbound side effects).
- **No scheduler** (no cron, no background triggers).
- **No automation** (dry-run is always user-triggered).
- **No agents** (no autonomous decision-making; steps are deterministic or read-only).
- **No UI** beyond existing shell (FE-11 consumes these APIs separately).
- **No real execution** (Phase 2 — BE-20).

---

## 2. Data Model

All tables are **org-scoped** via `org_id`. Audit convention: `created_at`, `updated_at` (timestamptz); where relevant `created_by` (uuid → auth.users).

### 2.1 workflow_defs

Stored workflow definitions (read-only in Phase 1 from API; may be seeded or created via admin/CLI).

| Column        | Type         | Constraints                          |
|---------------|--------------|--------------------------------------|
| id            | uuid         | PK, default gen_random_uuid()        |
| org_id        | uuid         | NOT NULL, FK → organizations(id)    |
| name          | text         | NOT NULL                             |
| description   | text         | optional                             |
| definition    | jsonb        | NOT NULL (schema below)              |
| schema_version| text         | NOT NULL (e.g. `"2025.1"`)           |
| created_at    | timestamptz  | NOT NULL, default now()              |
| updated_at    | timestamptz  | NOT NULL, default now()              |
| created_by    | uuid         | optional, FK → auth.users(id)        |

- Indexes: `(org_id)`, `(org_id, updated_at)`.
- RLS: org-scoped SELECT; Phase 1 no INSERT/UPDATE via public API (manual seed or later module).

### 2.2 workflow_runs

One row per invocation (dry-run or, in Phase 2, real execution). Every dry-run creates a run.

| Column        | Type         | Constraints                          |
|---------------|--------------|--------------------------------------|
| id            | uuid         | PK, default gen_random_uuid()        |
| org_id        | uuid         | NOT NULL, FK → organizations(id)    |
| workflow_id   | uuid         | NULL for ad-hoc dry-run by definition; FK → workflow_defs(id) when run by stored def |
| run_type      | text         | NOT NULL: `dry_run` \| `execute` (Phase 2) |
| status        | text         | NOT NULL: `running` \| `completed` \| `failed` \| `cancelled` |
| triggered_by  | uuid         | NOT NULL, FK → auth.users(id)        |
| definition_snapshot | jsonb | NOT NULL (definition at run time for reproducibility) |
| parameters    | jsonb        | optional (inputs passed at run time) |
| created_at    | timestamptz  | NOT NULL, default now()              |
| completed_at  | timestamptz  | optional                             |
| error_message | text         | optional (safe, no PII)               |

- Indexes: `(org_id)`, `(org_id, created_at)`, `(workflow_id)`, `(run_type)`.
- RLS: org-scoped; SELECT/INSERT by backend with org_id from auth.

### 2.3 workflow_steps

One row per step execution within a run. Full trace for audit and preview.

| Column        | Type         | Constraints                          |
|---------------|--------------|--------------------------------------|
| id            | uuid         | PK, default gen_random_uuid()        |
| run_id        | uuid         | NOT NULL, FK → workflow_runs(id) ON DELETE CASCADE |
| step_index    | int          | NOT NULL (order within run)          |
| step_name     | text         | NOT NULL (from definition)            |
| step_type     | text         | NOT NULL (e.g. `rag_retrieve`, `transform`, `condition`) |
| status        | text         | NOT NULL: `pending` \| `running` \| `completed` \| `failed` \| `skipped` |
| input_snapshot| jsonb        | optional (input passed to step; redact if sensitive) |
| output_snapshot| jsonb       | optional (predicted or actual output; dry-run = predicted) |
| error_message | text         | optional (safe)                      |
| started_at    | timestamptz  | optional                             |
| completed_at   | timestamptz  | optional                             |
| created_at    | timestamptz  | NOT NULL, default now()             |

- Indexes: `(run_id)`, `(run_id, step_index)`.
- RLS: via run → org; no direct org_id on row (query through workflow_runs).

### 2.4 audit_events (workflow-scoped)

Minimal event log per run for BE-11; may be unified with BE-12 `audit_events` in implementation (same table with `resource_type = 'workflow_run'` and `resource_id = run_id`).

| Column         | Type         | Constraints                          |
|----------------|--------------|--------------------------------------|
| id             | uuid         | PK, default gen_random_uuid()        |
| org_id         | uuid         | NOT NULL                             |
| action         | text         | NOT NULL (e.g. `workflow.dry_run.started`, `workflow.dry_run.completed`, `workflow.dry_run.step_completed`) |
| actor_id       | uuid         | NOT NULL, FK → auth.users(id)        |
| resource_type  | text         | NOT NULL (e.g. `workflow_run`)      |
| resource_id    | uuid         | NOT NULL (run_id)                    |
| metadata       | jsonb        | optional (run_type, workflow_id, step_index; no PII) |
| created_at     | timestamptz  | NOT NULL, default now()             |

- Indexes: `(org_id, created_at)`, `(resource_type, resource_id)`.
- RLS: org-scoped SELECT; INSERT via service role or backend only.
- **No query text, no embeddings, no user-provided content in metadata** (safety).

---

## 3. Workflow Definition Schema (Minimal, Versioned)

### 3.1 Schema Version

- Top-level `schema_version` (e.g. `"2025.1"`) required.
- Backend rejects definitions with unknown version (400).

### 3.2 Structure (Normative)

```json
{
  "schema_version": "2025.1",
  "name": "Optional display name",
  "steps": [
    {
      "id": "step_1",
      "name": "Retrieve context",
      "type": "rag_retrieve",
      "config": {
        "query_input_key": "query",
        "top_k": 10
      }
    },
    {
      "id": "step_2",
      "name": "Format result",
      "type": "transform",
      "config": {
        "template": "Summarize the following: {{steps.step_1.output}}"
      }
    }
  ]
}
```

- **steps:** Ordered array. Execution order = array order.
- **step.id:** Unique within definition (string key for referencing).
- **step.name:** Human-readable; used in run trace and UI.
- **step.type:** Determines handler and dry-run semantics (see below).
- **step.config:** Type-specific; validated per type.

### 3.3 Step Types (Phase 1 — BE-11)

| Type           | Description                     | Dry-run behavior |
|----------------|---------------------------------|------------------|
| `rag_retrieve` | Call BE-10 retrieval (read-only)| **Real** read: call POST /api/rag/retrieve (or internal service), store predicted output in step trace. No write. |
| `transform`    | Pure function over prior outputs| **Simulated:** evaluate template/expression over previous steps’ outputs; result = predicted output. No I/O. |
| `condition`    | Branch on expression            | **Simulated:** evaluate condition; output = branch chosen; no side effect. |
| `noop`         | Placeholder / manual step       | **Simulated:** output = stub message. |

- **Extensibility:** New step types require schema and handler registration; no dynamic code execution from definition.

### 3.4 Idempotency & Determinism

- Dry-run must be **deterministic** for same definition + same parameters (where step is read-only). RAG step: same query → same retrieval result within same org/source state.
- No randomness in trace output unless explicitly documented (e.g. "sample one of N").

---

## 4. API Contracts

### 4.1 POST /api/workflows/dry-run

- **Auth:** Required (BE-00). Org from auth context only; no `org_id` in body.
- **Request body:**
  - `definition` (object, required): workflow definition JSON (schema above), or
  - `workflow_id` (uuid, optional): reference to stored `workflow_defs.id` (org-scoped); if present, server loads definition from DB and ignores body `definition`.
  - `parameters` (object, optional): key-value inputs (e.g. `query`) for steps that accept input.
- **Behavior:**
  - Validate definition (schema_version, steps, types, config).
  - Create `workflow_runs` row: `run_type = dry_run`, `status = running`, `definition_snapshot`, `parameters`, `triggered_by`, `org_id`.
  - Emit audit event: `workflow.dry_run.started`.
  - For each step in order: create `workflow_steps` row (pending → running → completed/failed); compute **predicted output** (rag_retrieve = real read; transform/condition/noop = simulated); set `output_snapshot`; emit `workflow.dry_run.step_completed` (or step_failed).
  - Update run: `status = completed` or `failed`, `completed_at`; emit `workflow.dry_run.completed`.
- **Response (200):**
  - `run_id` (uuid)
  - `status` (`completed` | `failed`)
  - `plan` (optional): ordered list of step names/ids.
  - `steps` (array): `[{ step_name, step_type, status, predicted_output? }]` (or equivalent; align with `workflow_steps` shape).
  - `errors` (array, optional): validation or step errors (safe messages only).
- **Errors:**
  - 400: Invalid definition or parameters (validation failure).
  - 401: Missing/invalid auth.
  - 403: Valid auth but no org context.
  - 404: `workflow_id` provided but not found or not in org.
  - 503: RAG or internal dependency unavailable during dry-run (safe message; do not return partial run as success if critical step failed).

### 4.2 GET /api/workflows/runs/:id

- **Auth:** Required. Org from auth; may only access runs for own org.
- **Response (200):**
  - Run record: `id`, `workflow_id`, `run_type`, `status`, `triggered_by`, `definition_snapshot`, `parameters`, `created_at`, `completed_at`, `error_message`.
  - `steps`: array of step records (id, step_name, step_type, status, input_snapshot, output_snapshot, error_message, timestamps).
  - Optional: `audit_events` (or link to BE-12 GET /api/audit filtered by resource_id = run_id).
- **Errors:**
  - 401/403: as above.
  - 404: Run not found or not in org.

### 4.3 GET /api/workflows (List)

- **Auth:** Required. Org-scoped.
- **Response (200):** `{ workflows: [{ id, name, schema_version, updated_at }] }` from `workflow_defs` for org. Phase 1 read-only; no create/update via API.

### 4.4 GET /api/workflows/:id (Definition Detail)

- **Auth:** Required. Org-scoped.
- **Response (200):** Full workflow definition + metadata (id, name, definition, schema_version, created_at, updated_at). 404 if not in org.

---

## 5. Security

### 5.1 Org Scoping

- **All access:** Org is derived from BE-00 auth context only (JWT → organization_members → org_id). Request body must **not** accept `org_id` for access control.
- **workflow_defs:** SELECT restricted to rows where `org_id` = auth org.
- **workflow_runs:** INSERT with `org_id` from auth; SELECT only runs for auth org.
- **workflow_steps:** Accessed only via run_id; run must belong to auth org.
- **audit_events:** Org-scoped; no cross-org visibility.

### 5.2 Service Role Rules

- Backend may use Supabase **service role** for INSERT into workflow_runs, workflow_steps, audit_events (and for reading RAG in dry-run). Service role **must** only be used server-side; `org_id` and `triggered_by` must be set from authenticated request context, never from client-supplied values for authorization.
- RLS policies still apply to anon/key; service role bypasses RLS but application code enforces org and user context.

### 5.3 Input Sanitization

- Definition and parameters are validated and size-limited. No arbitrary code or script in definition. Step configs are type-checked per step type.
- Audit event metadata: no user-provided free text that could contain PII; only structured fields (run_id, step_index, status, etc.).

---

## 6. Dependencies on BE-10 (RAG)

- **RAG retrieval step:** When a step has `type: "rag_retrieve"`, dry-run invokes the same retrieval path as BE-10 (internal call or same service): same org filter, same citation shape. The step’s **predicted output** is the actual retrieval result (chunks + query_id). This is the only "real" I/O in dry-run; it is read-only and already org-scoped.
- **Failure handling:** If RAG returns 503 or times out, the dry-run step is marked failed; run status = failed; response 503 with safe message (no partial run presented as success).
- **No generation:** BE-10 has no LLM generation; dry-run does not add generation. If a future step type "llm_generate" is added, it would be out of scope for BE-11 until specified.

---

## 7. "Approvals Required" Boundary (Phase 2)

- BE-11 does **not** implement approvals. The plan only **defines the boundary**: when `run_type = execute` is introduced (BE-20), the same tables (`workflow_runs`, `workflow_steps`, `audit_events`) will be used; an approval gate (e.g. required role or explicit approve endpoint) will be required before transitioning a run from "pending_approval" to "running" for execution.
- Dry-run records provide a **trace** that can be referenced in Phase 2 for "run like this dry-run" or for approval context (e.g. show last dry-run result before execute).

---

## 8. Stop Conditions & Open Questions

**Implementation must STOP and ask if:**

1. **Workflow definition schema not closed:** Step types beyond `rag_retrieve`, `transform`, `condition`, `noop` are needed for Phase 1 and not yet specified (config shape, validation rules).
2. **Dry-run semantics for a step type unclear:** e.g. whether a step should call real read (RAG) vs stub; decision must be documented.
3. **Audit event schema conflicts with BE-12:** If BE-12 defines a single `audit_events` table with different columns or action enum, BE-11 and BE-12 must align (shared table vs workflow-specific table and sync).
4. **RLS design for workflow_steps:** Steps have no direct `org_id`; access is via join to `workflow_runs`. Policy must enforce org without leaking other orgs’ run data.
5. **Scope expansion:** Any request to add external calls, scheduling, or automation in BE-11 — reject and refer to Phase 2/3.

**Open questions (from MASTER plan):**

- **OQ-3:** Workflow definition schema: JSON structure, step types, validation rules — this plan specifies a minimal schema; extend only with approval.
- **OQ-4:** Dry-run semantics: stub vs real read-only — this plan specifies: **real read for RAG only**; all other step types simulated/stub.

---

## 9. Acceptance Criteria (Summary)

- [ ] Workflow definition schema is versioned and validated; unknown version or invalid steps return 400.
- [ ] POST /api/workflows/dry-run creates a run and step records; returns run_id, status, plan, and predicted outputs; no writes outside workflow_runs, workflow_steps, and audit_events.
- [ ] GET /api/workflows/runs/:id returns run and steps for the authenticated org only.
- [ ] RAG step in dry-run calls BE-10 retrieval (org-scoped) and stores result as step output; no generation.
- [ ] All access is org-scoped from auth; no org_id in request body for authorization.
- [ ] Audit events are written for dry_run started, step completed/failed, dry_run completed; no PII or query text in events.

---

## 10. Non-Goals (Recap)

- No external actions, scheduler, automation, or agents.
- No UI beyond existing shell.
- No real workflow execution (Phase 2).
- No LLM generation in BE-11.
