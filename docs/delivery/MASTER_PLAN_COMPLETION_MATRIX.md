# Master plan completion matrix (authoritative)

**Branch / draft:** [`cursor/full-release-implementation-6b92`](https://github.com/cesarbohjr/gravitre-saas-backend/pull/429)  
**Cohesion rules:** [`PLATFORM_COHESION.md`](./PLATFORM_COHESION.md) · **Split plan:** [`PR429_DEPENDENT_SPLIT.md`](./PR429_DEPENDENT_SPLIT.md)  
**Current implementation:** `codex/master-plan-completion-20261014` (based on #429 at `7fd10c4a`); see [Codex implementation evidence](./CODEX_IMPLEMENTATION_2026-10-14.md). Earlier row statuses below require reconciliation against that increment.

**2026-10-16 resolved MCP approvals (draft):** the existing shared approval
queue now reviews the exact persisted MCP arguments and dispatches through the
existing single-use consume path. Tool schema/name, server endpoint/transport and
credential version are bound to consent; changes require fresh review. An approved
but unconsumed proposal can resume; a consumed proposal cannot be sent twice.
Agent permission is revalidated. MCP write acceptance never claims independent
verification. Local focused tests pass; real-DB race and production acceptance
remain open. Dynamic workflow argument pause/review/resume is still open.
The model-evaluation warning-log defect is corrected locally; full CI must rerun.

**Railway configuration setup (2026-10-16 UTC):** nine previously absent
production backend variables are now explicitly set, with deployments skipped.
New feature activation is pinned off, write authority is `shadow`, and queue
fail-closed is `true`. Names were verified after the write; OAuth redacts value
readback. Existing flags were not overwritten. Running deployment remains
`b642dd156`; saved values apply on the next deployment. This does not activate
the new release. See [configuration receipt](./railway-production-flags-2026-10-16.json).

**Production migration update (2026-10-16 UTC):** all six approved migrations
are applied and schema/role grants verified in `smyeexlrqdpymwjmgzqu`. Supabase
assigned versions `20261016032007`, `032018`, `032029`, `032039`, `032048`, and
`032109` (same date prefix). Repository files are renamed to those exact versions
without SQL changes; DB test paths follow them. Earlier pending-migration labels
below are historical and superseded by this update. No activation flags were
changed and no historical billing recovery was run. This is schema acceptance,
not full application acceptance. See [apply receipt](./supabase-migrations-applied-2026-10-16.json).
Current CI at `eacb3d57` passed all dedicated PG/Redis and focused gates, but the
full backend finished **11,066 passed, 7 skipped, 1 failure**: missing warning
logging in the model evaluation harness. Clean reset still fails at the older
`20250220000006` function return-type change. Both release gates remain open.

**Current closeout evidence (2026-10-15):** #431 at `7ad397d` passed full backend
CI (**11,006 passed, 7 skipped**), web lint/typecheck/build/tests, shared text/voice,
integration smoke, required PostgreSQL billing/idempotency gates and Redis gates
in [38817159040](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/38817159040).
Billing Playwright was skipped. Migration validation passed; the clean reset
remains blocked at historical `20250220000006`. Earlier red CI entries below
are historical evidence, superseded by this run, not current blockers.

**Latest full regression:** #431 at `312fe812` passed CI run 38824440821 with
**11,027 backend tests passed, 7 skipped**, web tests/lint/typecheck/build,
shared text/voice and integration smoke. Dedicated recovery (6 PG + 11 context/
scheduler tests) and company source revocation (15 focused tests) passed.
Billing Playwright remains skipped; production acceptance remains open.

**Segment regression integrity:** invalid identify/group user/group IDs are
refused before HTTP dispatch. Ten synthetic tests passed with `_request` mocked
and invalid requests asserting no call. The broad local connector run was
stopped after automatic approval review blocked an unverified Segment request;
no broad-suite PASS is claimed. Full CI remains required.

**2026-10-16 focused acceptance:** 178 local tests passed across credential
scope/disconnect, memory lineage/liveness, approval projection/fingerprints and
run authority. The writer inventory decreases by exactly four removed untagged
fallback sites; its exact-count guard is retained. Production schema read-only
checks show none of the six repository migrations dated October 14 onward
recorded, no new ledger tables or recovery columns, and existing run/turn IDs.
See [evidence](./platform-integrity-closeout-2026-10-16.json). Full CI remains pending.

**2026-10-16 run-authority revalidation:** the shared catalog invoke spine
revalidates declared run authority against an org-scoped, live approved run with
at least one required approval. A missing/rejected run or mismatched reference
cannot bypass scope validation; the loaded row is reused for argument checks.
Unit and invoke-spine tests added; CI pending. Human/policy/compensation authority
semantics are unchanged. No schema or runtime flag changes.

**2026-10-16 lineage integrity correction:** tagged agent/workspace/temporal
memories and entity observations no longer retry failed writes with their source
columns removed. External agent-memory creation also requires valid lineage
before embedding when the flag is on, matching workspace promotion; user-direct
memories keep their existing behavior. This preserves future disconnect/revocation filtering when
`MEMORY_SOURCE_LINEAGE_ENABLED` is enabled. Untagged legacy writes retain their
existing compatibility behavior. Missing-schema and commit/timeout tests enforce
one tagged attempt and no untagged fallback. No migration or flag change; focused
and full CI acceptance pending. Document lineage and legacy classification remain
open and are not claimed closed by this correction.

**2026-10-16 approval loader correction:** the canonical run loader now selects
`definition_snapshot`, which canvas/ReAct/tool invocation use to verify the
reviewed definition digest. Projection-aware ReAct tests exercise the real loader:
reviewed arguments reach the registry once; changed arguments or definitions
never reach it; a foreign-org run is not returned. No schema or flag change.
CI run 38841395865 at `004d0118` passed the PG gates and 54 credential-focused
tests, but failed one old disconnect mock lacking the new required `org_id`.
The mock now asserts tenant scope explicitly; the full suite still needs rerun.

**Next draft increment:** durable assistant recovery snapshots credits and
allowance on `model_calls`; the existing usage scheduler invokes a bounded,
replica-safe recovery RPC. Migration `20261015232327` and default-off
`ASSISTANT_BILLING_RECOVERY_ENABLED` are not applied/activated. Its required
PostgreSQL gate passed in CI run 38823949550 at `8038f11b`; full regression
acceptance is separate. A changed period allowance blocks settlement for review; old calls,
closed-month recovery, historical overage and plan-change economics remain open.
See [closeout queue](./MASTER_PLAN_CLOSEOUT_2026-10-15.md).

**2026-10-15 draft extension:** atomic assistant usage + overage RPC migration
`20261015032117` and default-off `ASSISTANT_BILLING_ATOMIC_ENABLED`; real-Postgres
acceptance passed in CI [38678073767](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/38678073767), not applied. All other usage sources still
use the legacy nontransactional path. A crash-gap report exists, but automated
recovery (manual bounded command only), historical backfill, plan changes within a period and production
acceptance remain open. Do not count this as fully reconciled billing.

`20261015222156` and default-off `USAGE_ATOMIC_ENABLED` extend the transaction
lock to other app writers. The mixed-source Postgres gate, historical overage
audit and production acceptance remain open. The generic flag must be enabled
before assistant-specific atomic billing, after both migrations pass staging.

The bounded recovery command on #431 now compares assistant usage rows with
measured calls, refuses mismatched or truncated preflight windows, and flags
zero-token charges. Workflow ROI reads paginate, and mark costs, counts and
wait time unknown when coverage is incomplete. CI [38678073767](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/38678073767)
had **10,994 backend passes, 7 skips and one row-cap boundary failure**;
that boundary fix is on #431 pending a complete rerun. None of this is
production acceptance. The old `20250220000006` migration still blocks a
clean `supabase db reset` replay; the new SQL passed migration validation and
its dedicated disposable-Postgres test.

**Last updated:** 2026-10-14 (CI fixes pushed `8d990d685`; prior evidence `617c0a10d`)  
**Legend — implementation:** `NOT STARTED` · `PARTIAL` · `CODE COMPLETE` · `MERGED` · `DEPLOYED`  
**Legend — acceptance:** `NOT RUN` · `PARTIAL` · `PASS` (evidence-linked only)

Columns: **Impl** · **PR / commit** · **Tests executed** · **Migrations** · **Config / flags** · **Production acceptance** · **Blocker**

**Latest draft evidence:** [#431](https://github.com/cesarbohjr/gravitre-saas-backend/pull/431) at `f7585d8a`. CI [38600879096](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/38600879096) passed web tests, typecheck/build, 9 real-Postgres claim tests and 9 real-Redis queue tests; full backend had **83 failures, 10,886 passes, 7 skips**. Scenario fake-PostgREST revision handling and approval test fixtures caused most new failures and are corrected in the next draft increment pending CI. The [migration replay run 38600880008](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/38600880008) passed validation but clean `supabase db reset` failed at the older `20250220000006` migration attempting to change a function's return type via CREATE OR REPLACE. Production acceptance and migration application remain open.

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
| Canonical connector-secret tenant scope | CODE COMPLETE (draft) | Required org_id for single/bulk secret, OAuth and masking helpers; 126 app callsites updated | Syntax + scope inventory passed; focused tenant/mixed-bulk tests pending CI | None | Mandatory scoping, no flag | NOT RUN | Full vendor regression and authenticated connector proof |

**Release 1 gate:** OPEN — authenticated prod matrix not evidence-linked.

---

## 2. Release 2 — approvals, binding, idempotency, queue, lifecycle, durability

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| Workflow approval digest + missing scope | CODE COMPLETE | #429 | `test_workflow_approval_scope_audit.py` (local PASS via gates script) | — | — | NOT RUN | Merge |
| Action-specific argument sealing | CODE COMPLETE | `eb4b16c93` | `test_write_approval_fingerprints.py` | — | — | NOT RUN | Dynamic chat/voice still OPEN |
| Claim token + stale finalize fence | CODE COMPLETE | `eb4b16c93` | PG `test_write_invoke_idempotency_pg.py` (CI gate; local skip) | `20261014100000` + `100001` grants | `WRITE_INVOKE_IDEMPOTENCY_ENABLED=false` | NOT RUN | Migration not applied prod |
| Expired lease → uncertain / reconcile | CODE COMPLETE | `eb4b16c93` | PG tests | Same | Same | NOT RUN | — |
| Redis queue ownership / ack / recovery | CODE COMPLETE (single Redis) | Codex branch | Real Redis: atomic movement, process kill, stale owner, competing consumers, poisoned job | — | Queue off; queued writes require idempotency enabled | NOT RUN | Staging rollout; legacy processing reconciliation; Redis Cluster not supported |
| Lifecycle envelope backend | CODE COMPLETE | `617c0a10d` | `test_lifecycle_envelope.py` | — | — | NOT RUN | — |
| Lifecycle consumers (web) | CODE COMPLETE | Codex branch | Full web suite 1,735 passed; typecheck/build pass | — | — | NOT RUN | Authenticated UI and late verification proof |
| Write authority enforce (not shadow) | PARTIAL (main) | #414 shadow | — | — | — | NOT RUN | Product flip |
| Stale run recovery (#421) | PARTIAL | main, flag off | — | — | — | NOT RUN | ~19 stuck runs disposition |

**Release 2 gate:** OPEN — PG/Redis CI green + prod trace after merge/apply.

---

## 3. Chat / voice quality, latency, context, sentiment, ML, revocation

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| Turn tracing + shared context artifact | PARTIAL | Existing cognitive trace/critical-path audits + #431 model-call correlation; no separate context artifact | Existing trace tests; context manifest still open | — | — | PARTIAL | Root-to-provider spans and context coverage |
| P50/P95 latency proof | PARTIAL | Existing baseline reporter; read-only 30-day production aggregate in latency-production-baseline-2026-10-15.json | 1,059 text / 364 voice correlated turns | — | No flags changed | PARTIAL | Compose timing only; browser/first-audio and same-revision SLO proof open |
| Connector lineage enablement | NOT STARTED | — | — | — | — | NOT RUN | — |
| Memory / document lineage / resurfacing | PARTIAL | Existing recall liveness; draft company snapshot fingerprint/liveness recheck | New snapshot revoke/edit/retire tests pending CI | Existing lineage migration | MEMORY_SOURCE_LINEAGE_ENABLED unchanged | NOT RUN | Document lineage, historical summaries, other cache paths; STA-312 / Memory Option B |
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
| ReAct / unified-turn tool metering | PARTIAL | Codex branch | Canonical writer, cache tokens, turn/run context tests pass | Existing attribution migration | — | NOT RUN | Failure/cancel usage; billing reconciliation; production row proof |
| Streamed-turn charge from persisted model calls | PARTIAL (per-call measured credits in next draft) | #431 follow-on | Focused mocked route and ledger tests | Existing `model_calls`/usage schema | — | NOT RUN | Durable crash reconciliation; historical backfill; DB concurrency |
| Metering reconciliation / ROI caps / PSA | PARTIAL (streamed charge only) | #431 follow-on | Focused unit | — | — | NOT RUN | Durable sweep, ROI/PSA baselines, production evidence |

---

## 5. Model catalog, pricing, evaluations, routing economics

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| Catalog / pricing | CODE COMPLETE for Haiku/Sonnet slice | Codex branch | Haiku 100k threshold and cache-write pricing; selector/catalog parity | — | Existing routing defaults | NOT RUN | Model quality evaluations and complete pricing refresh |
| Budget caps + adaptive routing | PARTIAL (existing non-atomic policy/budget checks; new direct-provider gate in draft) | #431 next increment | Targeted regressions pending | — | No production activation | NOT RUN | Policy lookup is best effort; no atomic budget reservations or quality evidence |
| Briefing evals (Haiku / Argon / etc.) | PARTIAL | Draft bounded synthetic workflow comparison using existing ModelRouter/model_calls | Focused evaluation tests pending CI; no live model requests | — | Explicit CLI --run only | NOT RUN | Representative task corpus, live provider evidence, routing thresholds; no routing change |

---

## 6. Release 4 — MSP delegation, switching, isolation

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| `parent_org_id` scaffold | PARTIAL (relationship only; explicit client membership required) | #429 + Codex branch | `test_msp_org_context.py` denies parent-only access | `20261014060000` (review) | `MSP_PARENT_ORG_ENABLED=false` | NOT RUN | Apply authorization |
| Parent RLS path | WITHDRAWN | `MSP_RLS_PARENT_ACCESS_DEFERRED.md` | — | `20261014110000` removed | — | N/A | Product Option A/B |
| Workspace/client selection for explicit memberships | CODE COMPLETE (existing) | workspace-switcher.tsx + organizations switch route; no implicit parent delegation | Existing suite; authenticated switching acceptance open | None | Existing membership authority | NOT RUN | Cross-org cache/credential acceptance |
| MSP partner program (wholesale + rebilling, client consent, health-only delegation) | CODE COMPLETE | `routers/msp_program.py`, `billing/msp_billing.py`, Settings › Clients | `test_msp_program.py`, `db/test_msp_partner_program_pg.py`, `msp-clients.test.tsx` | `20261019120000` (not applied) | `STRIPE_PRICE_ID_MSP_*_WHOLESALE` unset = "not set up" state | NOT RUN | Apply migration (approval), create wholesale Prices, two-client acceptance on gravitre.app |
| External MCP product for MSPs | NOT STARTED | — | — | — | — | NOT RUN | External auth design |

---

## 7. External MCP, API keys, OAuth, plugins, distribution

| Item | Impl | PR / commit | Tests executed | Migrations | Config | Prod acceptance | Blocker |
|------|------|-------------|----------------|------------|--------|-----------------|---------|
| MCP tool bridge (backend) | PARTIAL | main | `test_react_mcp_tools.py` | — | — | NOT RUN | Distribution |
| API keys / OAuth surfaces | NOT STARTED for backend authorization | Frontend scaffolds only | No external-auth acceptance | — | — | NOT RUN | Secure backend key/token lifecycle and OAuth implementation |
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
