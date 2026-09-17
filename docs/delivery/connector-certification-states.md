# Connector certification states (Section R) — product / process

**Status:** PROCESS ONLY — no schema, no runtime state machine, no customer UI  
**Date:** 2026-09-17  
**Anchor:** [connector-action-wiring-audit.md § R](./connector-action-wiring-audit.md#r-future-connector-acceptance-standard-proposed--not-implemented) and invariant **R** (“Connected” ≠ all actions available)  
**Does not expand F1. Does not change WRITE inference or G8.**

This document defines **how engineering and product treat connector readiness**. It does **not** ship a customer-visible “certified / TRAINED / live” badge, price, or Enable toggle. Those remain unauthorized product surface unless a later conversation explicitly requests a customer UI and confirms it as real.

---

## Why this is process, not a flag

Invariant R failed as **PARTIAL** because `evaluate_connector_availability(action_key=…)` exists, but planners did not always consult it, and operators still collapse many layers into “the connector is connected.”

Section R proposed a single ladder:

`REGISTERED → CONFIGURED → CONNECTED → CAPABILITY_READY → ACTION_READY → PRODUCTION_VERIFIED`

That ladder mixed **three different objects**. Collapsing them into one customer or database flag recreates the original bug.

| Track | Object | Question | Existing signals (do not invent new customer copy) |
|-------|--------|----------|----------------------------------------------------|
| **A. Catalog acceptance** | Vendor / action in the product catalog | May Gravitre *claim this action as a supported business task*? | `ActionSpec`, `implementationStatus`, `verificationClaim`, capability bindings, schema lint |
| **B. Tenant execution** | One org’s connector row | Can *this org* run *this action now*? | `display_status`, `execution_available`, scopes, `CAN_THIS_ACTION_EXECUTE_NOW` |
| **C. Partner marketplace** | Partner submission | May a *partner* publish a connector to marketplace track 2? | `partner_connector_registry` sandbox / certification — **separate program**; do not merge into A/B |

**Product rule:** Track B answers “can we run it for this customer this turn.” Track A answers “is the platform honest that this action is a supported task.” Track C is marketplace ingest. None of these is a customer “Certified” chip.

---

## Track A — catalog acceptance (engineering)

Apply **per action**. A vendor is only as ready as its weakest **advertised** action. Do not promote a vendor to `PRODUCTION_VERIFIED` because one happy-path READ works.

Internal state names (engineering vocabulary; **not** UI labels):

### 1. `REGISTERED`

**Meaning:** The action exists in `vendor_definitions` / `action_catalog` with a stable `vendor.resource.verb` id.

**Promote when:** Catalog lint passes naming / description / kind (see `docs/engineering/connector-action-schema-standard.md`).

**Nearest code today:** row present in catalog audit JSON.

**Not enough for:** chat attach, customer “connected,” or “we support this task.”

### 2. `CONFIGURED`

**Meaning:** Auth *path* exists (tenant OAuth, API key, or gravitre-managed platform env). Partner-gated vendors stay here until the partner program unblocks — that is a **process hold**, not a UI “pending certification” badge.

**Promote when:** Connectors hub can collect the required credential class; callback/route exists where OAuth is the auth mode.

**Nearest code today:** auth mode + OAuth routes / secret slots. May 2026 readiness report is historical; re-verify before treating a vendor as configured.

**Not enough for:** execution. Catalog-only ghosts (`webhook.connectors.get`, `webhook.post.replay`) never leave `REGISTERED` / fail `CONFIGURED`+executor.

### 3. `CAPABILITY_READY`

**Meaning:** The action is either bound to a canonical capability (or recipe) **or** explicitly marked **action-only** (no business capability; must not be advertised as a named capability).

**Promote when:** `capability_ontology` binding exists, **or** a written “action-only — do not advertise as capability X” note in the catalog audit / recipe docs.

**Nearest code today:** 9 capabilities vs 732 actions (audit 2026-09-17). Unmapped actions are **not** capability-ready for autonomous business asks.

**Honesty:** Unmapped + chat-exposed is a **process defect** if marketing or the assistant implies a business capability.

### 4. `ACTION_READY`

**Meaning:** Gravitre can compile and invoke the action on a governed path without depending on model memory of tool names.

Mandatory gates (same list as audit § R; still **process** until architecture items 1–4 exist uniformly):

| Gate | Requirement |
|------|-------------|
| Executor | Registered in `invoke_tool` (not catalog-only) |
| Schema | One canonical schema (JSON / workflow / executor agree) |
| Parameters | Explicit source strategy for every user-facing required field |
| Preflight | Resource → params → scopes → constraints → governance before provider call (all chat paths, not only governed writes) |
| Errors | STA-303 classifiable failure, not generic “invalid parameters” |
| Isolation | Org-scoped credentials and audit |

**Nearest code today:** `implementationStatus=executable`, schema lint, write-authority flags. Dual-schema trinity and ReAct-first skip mean most long-tail actions are **not** process-`ACTION_READY` even when executable.

`CAN_THIS_ACTION_EXECUTE_NOW` is **Track B attach**, not Track A promotion.

### 5. `PRODUCTION_VERIFIED`

**Meaning:** Evidence-linked live PASS for the action (or a named representative of a verified class), after deploy, per `docs/ENGINEERING_STANDARDS.md`.

**Promote when:** Concrete pointer exists (`audit_events` timestamp + action, conversation/run id, CI live smoke artifact, or prod log with tool/request id). Pytest-only `verified_working` in catalog audit is **not** this state.

**Nearest code today:** audit `verificationClaim=verified_working` when `testStatus` is mock/live — that is **test coverage**, a **lower** bar than this process state. Confluence-class `no_tests` cannot be `PRODUCTION_VERIFIED`.

**Demote when:** Live class of failures reappears (HubSpot search-vs-list template) until repaired and re-proven.

---

## Track B — tenant execution (runtime, already partially implemented)

These are **org-instance** conditions. They must stay distinct from Track A so a customer who OAuth-connects HubSpot is not told every HubSpot action is ready, and so an expired token is not “not connected / not certified.”

| Process condition | Typical availability signals | Operator meaning |
|-------------------|------------------------------|------------------|
| Not connected | no row / disconnected / pending_auth | Connect first |
| Connected, not executable | `auth_expired`, `missing_scope`, misconfigured | Reconnect or grant scopes — **do not** ask for GA4 property / HubSpot id |
| Executable now (vendor) | `execution_available` | Vendor can run *some* actions |
| Executable now (action) | `evaluate_connector_availability(action_key=…)` + attach gate | This action can be offered to `tool_choice` |

Track B does **not** get new customer-facing state names in this pass. Existing Connectors / chat copy (connected, reconnect, connect) stays. Do not add “Capability ready” or “Production verified” to the hub.

---

## Track C — partner marketplace (out of scope to change)

Partner sandbox / registry certification is **track 2** (`docs/integration/agent-role-marketplace.md`). It answers “may this partner listing be published,” not “can this tenant’s HubSpot deals.search run.”

Do **not**:

- Reuse marketplace “certification badge” language on Connectors hub
- Treat partner publish as Track A `PRODUCTION_VERIFIED`
- Invent a second customer certification chip for first-party catalog vendors

---

## Who decides (named roles)

Until product names a different owner, promotions are:

| Decision | Owner | Not sufficient |
|----------|--------|----------------|
| Track A `REGISTERED` → `ACTION_READY` | Engineering (catalog + executor + schema) | Catalog row exists |
| Track A `PRODUCTION_VERIFIED` | Engineering + evidence-linked live PASS | Local pytest; audit JSON `verified_working` from tests |
| Advertise a **business capability** as supported | Product (written) + Track A `CAPABILITY_READY` on the bound actions | Model successfully guessing a tool once |
| Track B copy / hub status | Existing availability taxonomy (STA-303) | New badges |
| Track C publish | Existing marketplace / partner process | First-party catalog lint |

Schema-gate passing is **not** authorization to claim SOC 2, “certified connector,” or billable Enable (engineering standards §4 and §11).

---

## Operating rules

1. **Never collapse to “connected.”** Chat, workflows, and reviews must name the track: catalog gap vs tenant auth vs missing action scope vs unverified class.
2. **Advertise only `CAPABILITY_READY` + `ACTION_READY` actions** as autonomous business tasks. Everything else is “catalog present” or “connected but this action isn’t ready.”
3. **P0 ghosts** (`webhook.connectors.get`, `webhook.post.replay`) stay not-implemented until an executor exists; they cannot skip to verified.
4. **Unverified implemented (248 actions, 2026-09-17 matrix)** may be executable in registry and still **not** `PRODUCTION_VERIFIED`. Prefer not to expand customer-facing recipes onto that set.
5. **Writes** still require existing governance. Track A `ACTION_READY` includes the write gate; it does not bypass it.
6. **No customer surface in this document.** If a later UI is requested, it needs an explicit product decision listing exact strings. Default is **internal runbooks and audit JSON only**.

---

## Mapping cheat sheet (internal)

| If you see… | Treat as |
|-------------|----------|
| Catalog row, no `invoke_tool` | Track A ≤ `REGISTERED` |
| Executable, no tests | Track A ≤ `ACTION_READY` candidate; **not** `PRODUCTION_VERIFIED` |
| Tests only | Track A test-backed; live PASS still required for verified |
| Org OAuth connected | Track B connected; per-action still unknown |
| `execution_available=false` + expired auth | Track B reconnect; not “capability missing” |
| Capability id on the turn | Requires Track A `CAPABILITY_READY` for that id |
| Partner registry certified | Track C only |

---

## Explicitly not in this pass

- No new columns, enums, or migrations
- No Connectors hub / marketplace badge
- No Enable/Disable that looks like entitlement
- No change to `CAN_THIS_ACTION_EXECUTE_NOW` semantics (Track B attach only)
- No recertification cron or customer email

When architecture items (single schema, universal preflight, parameter source rules) land, **revisit** Track A `ACTION_READY` gates against those implementations — still without inventing customer certification chrome.
