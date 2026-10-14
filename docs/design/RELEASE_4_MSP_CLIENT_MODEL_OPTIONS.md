# Release 4 — MSP client model (decision required)

**Status:** NOT STARTED (no migrations until Cesar selects an option).

## Goal

One MSP account manages multiple end clients with isolation across connectors, credentials, jobs, approvals, memory, audit, billing, and reports.

## Options (expand/contract friendly)

### Option A — Child organizations

- Each client is a full `organizations` row linked to MSP via `parent_org_id` (new column) or partnership table extension.
- Pros: Reuses existing org-scoped RLS and billing keys.
- Cons: Cross-client aggregate reporting needs explicit grant paths; more rows to migrate.

### Option B — Client scope within MSP org

- Single MSP org; `client_id` on connectors, runs, memory, credentials (nullable = internal).
- Pros: Simpler MSP operator UX for switching client context in one login.
- Cons: Broad RLS rewrite; higher regression risk on every org-scoped query.

## Non-negotiables (either option)

- Wrong-client denial on reads/writes/API keys.
- Deliberate client selection in UI/API (no silent cross-client aggregation).
- Partner read grants (`federation`) are **not** a substitute for client isolation.

## Next step after decision

1. Versioned migration + staging preflight counts.
2. Backend org context resolver + UI client switcher.
3. Acceptance: two test clients under one MSP; cross-client attempts fail; authorized aggregate shows provenance.

**Blocked on:** named choice between Option A and Option B.
