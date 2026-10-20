# Release 4 — MSP client model

**Status (2026-10-19):** DECIDED — **Option A (child organizations)** with a wholesale partner program.
Owner decision (Cesar): MSPs pay Gravitre **wholesale** per client workspace and **rebill** clients at their own price.
Implemented in code, migration `20261019120000_msp_partner_program.sql` **not applied to production**
(needs human approval per migration governance). Production acceptance: **NOT RUN**.

What shipped (code):
- `organizations.account_type` (`standard` | `msp`), `msp_clients` (one live relationship per client,
  client cannot be an MSP), `msp_billing_accounts`, `org_billing.billing_source` / `billed_by_org_id`.
- API `/api/msp/program` (`backend/app/routers/msp_program.py`, `services/msp_program.py`): enroll, create
  client workspace (active immediately, MSP user is owner), link existing workspace (client **owner** approves
  with *full* = chosen MSP members added as admins, or *health only* = `msp_delegations` tier-1 grants), detach
  by either side, terms, rebilling list + CSV statement.
- Wholesale billing (`backend/app/billing/msp_billing.py`): one Stripe subscription per MSP, item quantity =
  active clients per tier (prorated); webhook mirrors MSP subscription status to every active client's
  `org_billing`. Env `STRIPE_PRICE_ID_MSP_{NODE,CONTROL,COMMAND}_WHOLESALE`; missing = honest "not set up" state.
- The parent link still grants no data access by itself; `MSP_PARENT_ORG_ENABLED` stays `false`.
- UI: Settings › Clients, client approval / "Managed by" card in Settings › Organizations, "Billed through"
  on Settings › Billing, white label inheritance, pricing `#msp`, docs `guides/how-to/msp-partner-program`.

The options analysis below is kept for the record.

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

**Decision:** Option A (see status above). Remaining: apply the migration with approval, create the wholesale Stripe Prices, and run authenticated two-client acceptance on gravitre.app.
