# P8-5: AI Operator Console UI

**Route:** `/operator`  
**Authority:** Gravitre_Brand_Alignment_Spec.md, Phase 8 scope  
**Focus:** Serious AI operations console. No Agents UI.

---

## Scope

- Build an implementation-ready UX spec for the AI Operator console.
- Enforce the approved direction:
  - Three-panel operator layout
  - Context Packs
  - Explainability + Permission Guardrails
  - Action Plans
- Reuse existing approvals and workflow execution APIs where possible.

## Non-Goals

- Agents selection, tuning, or marketplace UI.
- Connector creation/testing UI (admin-only UI is separate).
- Displaying raw secrets or connector credentials.
- Arbitrary “assistant chat” features.

---

## UX Specification

### Layout (three-panel)

- **Left: Context Packs**
  - Purpose: curate and validate context sources for the current action plan.
  - Shows pack list with status, provenance, and freshness.
  - Attach/detach packs to the active plan.
- **Center: Action Plans**
  - Purpose: draft, review, and execute a plan with step-level status.
  - Contains plan composer, step list, and run controls.
- **Right: Explainability + Permission Guardrails**
  - Purpose: make rationale, risk, and approval gates explicit.
  - Shows “why” per step and required approvals.

### Global header

- Environment selector (drives `X-Environment` for all requests).
- Org + role indicator (read-only).
- Session status badge: `Idle`, `Planning`, `Review`, `Awaiting approval`, `Executing`, `Paused`, `Completed`, `Failed`.

### Context Packs panel (left)

- **List view**
  - Pack card: name, source type, scope (org/env), last refresh, health indicator.
  - Status pill: `Ready`, `Stale`, `Missing`, `Restricted`.
- **Details drawer**
  - Pack summary, source lineage, allowed usage, and data sensitivity.
  - No secrets or raw connector data; metadata only.
- **Actions**
  - Attach/detach to plan.
  - Refresh (if permitted).
  - Restricted packs require approval prior to attach.

### Action Plans panel (center)

- **Plan composer**
  - Operator prompt field with guardrail hints.
  - “Generate plan” transitions to plan view.
- **Plan view**
  - Plan summary (goal, owner, created time).
  - Step list with statuses:
    - `Queued`, `Needs approval`, `Approved`, `Running`, `Done`, `Failed`, `Skipped`.
  - Step expansion shows inputs/outputs metadata and linked Context Packs.
- **Run controls**
  - `Request approval`, `Execute`, `Pause`, `Resume`, `Cancel`.
  - All actions gated by role and guardrails.

### Explainability + Permission Guardrails (right)

- **Explainability**
  - “Why this step” summary.
  - Evidence: which Context Packs or inputs informed it.
  - Assumptions and confidence level.
- **Guardrails**
  - Policy checks: data sensitivity, external calls, write actions, connector usage.
  - Required approvals and role restrictions.
  - Block reasons distinguish hard stop vs soft warning.
- **Approvals queue**
  - Pending approvals list with approve/reject (admin-only).

---

## Component Hierarchy (Blueprint)

```
OperatorPage
  ├─ OperatorHeader
  │   ├─ EnvironmentSelector
  │   ├─ OrgRoleBadge
  │   └─ SessionStatusBadge
  ├─ ThreePanelLayout
  │   ├─ ContextPacksPanel
  │   │   ├─ ContextPackList
  │   │   │   └─ ContextPackItem
  │   │   └─ ContextPackDetailsDrawer
  │   ├─ ActionPlanPanel
  │   │   ├─ PlanComposer
  │   │   ├─ PlanSummary
  │   │   ├─ PlanStepsList
  │   │   │   └─ PlanStepItem
  │   │   └─ PlanControls
  │   └─ ExplainabilityGuardrailsPanel
  │       ├─ ExplainabilityCard
  │       ├─ GuardrailsCard
  │       └─ ApprovalsQueue
  └─ OperatorToasts
```

---

## Data Flow Plan

### Existing APIs (reuse)

- Approvals
  - `GET /api/v1/approvals/pending`
  - `POST /api/v1/workflows/runs/:id/approve`
  - `POST /api/v1/workflows/runs/:id/reject`
- Execution
  - `POST /api/v1/workflows/execute`

### Required APIs (to define)

- Context Packs
  - `GET /api/v1/context-packs` (list for org + environment)
  - `POST /api/v1/context-packs/:id/refresh`
- Operator Plans
  - `POST /api/v1/operator/plans` (generate plan from prompt)
  - `GET /api/v1/operator/plans/:id`
  - `POST /api/v1/operator/plans/:id/approve-request`
  - `POST /api/v1/operator/plans/:id/execute`

### Flow (happy path)

1. Load `/operator` → fetch session, context packs, pending approvals.
2. Draft prompt → `POST /operator/plans` returns plan + steps + guardrails.
3. Attach context packs → updates plan context set.
4. Guardrails evaluate → steps marked `needs_approval` if required.
5. Request approval → appears in approvals queue.
6. Approval granted → steps unlock.
7. Execute → run begins, steps update status.
8. Completion → final status summary.

### Error handling

- Access denied (role) → clear message, no hidden controls.
- Guardrail block → show reason and required action.
- Backend failures → safe message only, no stack traces.

---

## State Model

### Page-level

- `idle` → no plan
- `planning` → generating plan
- `review` → plan created
- `awaiting_approval` → blocked on approvals
- `executing` → run active
- `paused` → paused run (if supported)
- `completed` → run finished
- `failed` → run failed

### Step-level

- `queued`
- `needs_approval`
- `approved`
- `running`
- `done`
- `failed`
- `skipped`

### Context Pack

- `ready`
- `stale`
- `missing`
- `restricted`

---

## Trust/Safety Model

- **Permission gating:** Approve/reject actions are admin-only.
- **Guardrail visibility:** Each step shows the policy triggers and why.
- **Sensitive data:** No secrets are returned or rendered. Metadata only.
- **Audit readiness:** Approvals and execution actions must be auditable.
- **Explicit blocks:** Hard stops show reasons; no silent failures.

---

## Recommended Implementation Order

1. Page skeleton + three-panel layout.
2. Context Packs list + attach/detach UI.
3. Plan composer + plan list UI.
4. Explainability panel (static rendering).
5. Guardrails panel + approvals queue.
6. Execute flow + live step status updates.
7. Polish: loading/error/disabled states.

---

## QA + UX Council Preview

### QA focus

- Environment scoping applied to all calls.
- Guardrail gating blocks execution correctly.
- Approvals require admin role.
- No secrets are rendered.
- Errors are safe and actionable.

### UX Council focus

- Three-panel layout feels operational, not “assistant chat”.
- Explainability is concise but sufficient per step.
- Guardrails are transparent, not surprising.
- Plan flow is clear: Draft → Review → Approve → Execute.
