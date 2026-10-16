# Master plan completion matrix (authoritative)

**Branch / draft:** [`cursor/full-release-implementation-6b92`](https://github.com/cesarbohjr/gravitre-saas-backend/pull/429)  
**Cohesion rules:** [`PLATFORM_COHESION.md`](./PLATFORM_COHESION.md) · **Split plan:** [`PR429_DEPENDENT_SPLIT.md`](./PR429_DEPENDENT_SPLIT.md)  
**Last updated:** 2026-10-14 (CI fixes pushed `8d990d685`; prior evidence `617c0a10d`)  
**Legend — implementation:** `NOT STARTED` · `PARTIAL` · `CODE COMPLETE` · `MERGED` · `DEPLOYED`  
**Legend — acceptance:** `NOT RUN` · `PARTIAL` · `PASS` (evidence-linked only)

Columns: **Impl** · **PR / commit** · **Tests executed** · **Migrations** · **Config / flags** · **Production acceptance** · **Blocker**

---

## 1. Release 1 — security and authenticated acceptance

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| Anonymous `/api/sessions` no org without auth | CODE COMPLETE | #429 `eb4b16c93` | Vitest `sessions-route-auth`, `require-authenticated-org` (CI `pnpm test` **NOT RUN** locally) | — | — | NOT RUN | Merge + gravitre.app matrix |
| Sanitized session errors (no DB leak) | CODE COMPLETE | `eb4b16c93` | Same | — | — | NOT RUN | — |
| Member / non-member / admin org gate | CODE COMPLETE | `requireAuthenticatedOrg` | Vitest (above) | — | — | NOT RUN | — |
| Role change / MCP stdio / retrieval +6m / watcher | PARTIAL (main) | #401–#411 merged | Various unit; full matrix NOT RUN | Through `20261013081000` applied | Relay off | NOT RUN | `release1-production-acceptance.md` + creds |
| Vercel `SUPABASE_SERVICE_ROLE_KEY` presence | NOT STARTED | — | — | — | — | NOT RUN | Operator |
| Deploy pair (web SHA = backend SHA) | PARTIAL | main vs #427 backend | `/health` `b642dd156` | — | — | PARTIAL | Vercel SHA reconcile |

**Release 1 gate:** OPEN — authenticated prod matrix not evidence-linked.

---

## 2. Release 2 — approvals, binding, idempotency, queue, lifecycle, durability

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| Workflow approval digest + missing scope | CODE COMPLETE | #429 | `test_workflow_approval_scope_audit.py` (local PASS via gates script) | — | — | NOT RUN | Merge |
| Action-specific argument sealing | CODE COMPLETE | `eb4b16c93` | `test_write_approval_fingerprints.py` | — | — | NOT RUN | Dynamic chat/voice still OPEN |
| Claim token + stale finalize fence | CODE COMPLETE | `eb4b16c93` | PG `test_write_invoke_idempotency_pg.py` (CI gate; local skip) | `20261014100000` + `100001` grants | `WRITE_INVOKE_IDEMPOTENCY_ENABLED=false` | NOT RUN | Migration not applied prod |
| Expired lease → uncertain / reconcile | CODE COMPLETE | `eb4b16c93` | PG tests | Same | Same | NOT RUN | — |
| Redis queue ack / requeue / poison | PARTIAL | `eb4b16c93` | Unit + `test_workflow_queue_redis_integration.py` (CI) | — | `EVENT_TRIGGER_USE_WORKFLOW_QUEUE=false` | NOT RUN | Multi-replica visibility |
| Lifecycle envelope backend | CODE COMPLETE | `617c0a10d` | `test_lifecycle_envelope.py` | — | — | NOT RUN | — |
| Lifecycle consumers (web) | PARTIAL | *this train* | `lifecycle-envelope.test.ts` | — | — | NOT RUN | Voice + ROI panels |
| Write authority enforce (not shadow) | PARTIAL (main) | #414 shadow | — | — | — | NOT RUN | Product flip |
| Stale run recovery (#421) | PARTIAL | main, flag off | — | — | — | NOT RUN | ~19 stuck runs disposition |

**Release 2 gate:** OPEN — PG/Redis CI green + prod trace after merge/apply.

---

## 3. Chat / voice quality, latency, context, sentiment, ML, revocation

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| Turn tracing + shared context artifact | NOT STARTED | — | — | — | — | NOT RUN | — |
| P50/P95 latency proof | NOT STARTED | — | — | — | Railway LIVE flags | NOT RUN | — |
| Connector lineage enablement | NOT STARTED | — | — | — | — | NOT RUN | — |
| Memory / document lineage / resurfacing | NOT STARTED | — | — | — | — | NOT RUN | STA-312 / Memory Option B |
| Source revocation complete | PARTIAL | main | Partial unit | — | — | NOT RUN | Audit paths |

---

## 4. Release 3 — webhooks, Freshservice, usage, metering, ROI

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| Signed webhooks + replay dedupe | MERGED (main) | #418 | Unit | `070000` applied | — | NOT RUN | — |
| HubSpot signature + test delivery | CODE COMPLETE (main) | #417 | Unit | — | — | NOT RUN | Live delivery |
| Freshservice trigger → run → approval | CODE COMPLETE (main) | #419 + UI panel | Unit | — | — | NOT RUN | No prod Freshservice connector |
| Event → workflow queue | CODE COMPLETE | #429 | `test_event_trigger_queue.py` | — | `EVENT_TRIGGER_USE_WORKFLOW_QUEUE=false` | NOT RUN | Flag off |
| `model_calls.turn_id` chat streaming | CODE COMPLETE | #429 branch | Unit | `080000` applied | — | NOT RUN | DB verify |
| ReAct `complete_with_tools` attribution | CODE COMPLETE | #429 (this train) | Gates script; dedicated test TBD | — | — | NOT RUN | Merge |
| Metering reconciliation / ROI caps / PSA | NOT STARTED | — | — | — | — | NOT RUN | Product |

---

## 5. Model catalog, pricing, evaluations, routing economics

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| Catalog / tier unit tests | PARTIAL | main | pytest catalog | — | — | NOT RUN | — |
| Budget caps + adaptive routing | NOT STARTED | — | — | — | — | NOT RUN | Release 7 scope |
| Briefing evals (Haiku / Argon / etc.) | NOT STARTED | — | — | — | — | NOT RUN | Third-party deps |

---

## 6. Release 4 — MSP delegation, switching, isolation

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| `parent_org_id` scaffold | PARTIAL | main | `test_msp_org_context.py` | `20261014060000` (review) | `MSP_PARENT_ORG_ENABLED=false` | NOT RUN | Apply authorization |
| Parent RLS path | WITHDRAWN | `MSP_RLS_PARENT_ACCESS_DEFERRED.md` | — | `20261014110000` removed | — | N/A | Product Option A/B |
| Client switcher / external MCP product | NOT STARTED | — | — | — | — | NOT RUN | UX + auth design |

---

## 7. External MCP, API keys, OAuth, plugins, distribution

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| MCP tool bridge (backend) | PARTIAL | main | `test_react_mcp_tools.py` | — | — | NOT RUN | Distribution |
| API keys / OAuth surfaces | PARTIAL | main | Route tests scattered | — | — | NOT RUN | — |
| Marketplace / plugins distribution | NOT STARTED | — | — | — | — | NOT RUN | — |

---

## 8. Briefing-linked evaluations and competitive comparisons

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| Competitive comparison artifacts | NOT STARTED | — | — | — | — | NOT RUN | Briefing sign-off |
| Third-party dependency proofs | NOT STARTED | — | — | — | — | NOT RUN | Vendor creds |

---

## CI / evidence checklist (#429)

Commit **`617c0a10d`** — run [38538270578](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/38538270578) @ `617c0a10df1dac8de82ed50e68d2a551f352c19c`

| Gate | Status | Evidence (counts) | Next action |
|------|--------|-------------------|-------------|
| `validate-migrations` | **PASS** | Job `115766653265` @ `617c0a10d` | — |
| PG idempotency acceptance | **PASS (0 skip)** | **9 passed** in job step (log ~08:57:11Z) | — |
| Redis queue integration | **PASS (0 skip)** | **5 passed** in job step (log ~08:57:18Z) | — |
| Full Backend pytest | **FAIL** | **10946 passed, 7 skipped, 1 failed** — `test_react_canvas_write_gate.py::test_canvas_run_approved_allows_write` (`approval_scope_missing`) | Fixed in working tree; re-run CI |
| Web unit tests | **FAIL** | **1726 passed, 1 failed** — `sessions-route-auth.test.ts` POST 503 vs 201 | Fixed in working tree |
| Shared runtime text/voice gate | **PASS** | Same run | — |
| Engineering gates script | **PASS (local)** | 52 passed — `release-engineering-gates.json` | Refresh on push |

**Migration apply order (not prod):** `20261014100000` → `20261014100001` (grants). Flags remain **off**.

---

## Stopping condition (not met)

Executable engineering continues on #429 until each row is **PASS** in production or carries a **named owner + handoff** for an external blocker. **Code complete ≠ merged ≠ deployed ≠ production accepted.**
