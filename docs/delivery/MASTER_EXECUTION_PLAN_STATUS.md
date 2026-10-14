# Master execution plan — cross-reference (2026-10-14, reconciled)

**Authoritative per-item matrix (implementation vs production acceptance):** [`MASTER_PLAN_COMPLETION_MATRIX.md`](./MASTER_PLAN_COMPLETION_MATRIX.md)

**Authoritative code:** `origin/main` @ `ce9c53b36`.  
**Merged implementation train:** PRs **#401–#421** (21 branches); **#422** adds migration `20261013081000` (same merge window as #421).

Legend: **COMPLETE** · **PARTIAL** · **NOT RUN** · **NOT STARTED** · **BLOCKED**

---

## 1. Baseline

| Item | Status | Evidence |
|------|--------|----------|
| Repo / PR heads match published locals | COMPLETE | All `claude/*` release tips are ancestors of `main` |
| Production Supabase migrations | COMPLETE (operator) | Through **`20261013080000`** applied; **`20261013081000`** applied (see below) |
| Web deploy | PARTIAL | Operator report: Vercel prod **`4a4397bb0`**; Cloud Agent HTML fetch shows `dpl_9P2FDxLiSMf9uV8ZvZAhy3zUwxWw` @ gravitre.app (2026-10-14) — confirm SHA in Vercel dashboard |
| Backend deploy commit | **VERIFIED (this session)** | `GET https://api.gravitre.app/health` and Railway host → **`git_sha=b642dd156`** @ `2026-10-14T05:25:02Z` |
| Pair alignment (web SHA = backend SHA = main) | **PARTIAL / mismatch risk** | Backend **`b642dd156`** (#427 automate) is **ahead of** reported web **`4a4397b`** (#423 illustrations). Reconcile before acceptance sign-off. |
| Railway flag effective values | PARTIAL | `/health` exposes unified-turn flags only; `DOMAIN_EVENT_RELAY_ENABLED` not in JSON — needs Railway dashboard or `railway_safety_vars` audit job |
| Vercel `SUPABASE_SERVICE_ROLE_KEY` presence-only | BLOCKED | Operator presence check |
| Post-merge production traffic | NOT RUN | Operator: last workflow run / model call **~14:09 UTC**, merge train **~17:54 UTC** — no proof new backend paths exercised in prod |

### Migration `20261013081000` (not in original six-pack)

**Source:** PR **#422** — *Make connector_action_availability read-only for org members* (`claude/project-thread-nokq9w`, merged 2026-10-13T17:54:53Z).

**Purpose:** Drop member **write** policies on `connector_action_availability`; members **SELECT** only. Prevents tampering with planner availability snapshots. File header notes it mirrors SQL already recorded in prod `schema_migrations`.

**Related migrations on main:** `20261013070000` (event trigger types), `20261013080000` (model_calls `run_id` / `turn_id` columns).

---

## 2. Release 1

| Item | Status | Evidence |
|------|--------|----------|
| **A. Publish** | COMPLETE (code) | Six fixes + four follow-ups **#401–#411**; merged in one batch (~2 min), not emergency-first with pause |
| **B. Scope review** | COMPLETE (code) | Pre-merge review / tests |
| **C. Migrations** | COMPLETE (prod) | `005000`–`060000` numeric order + operator postchecks; retrieval backfill counted; relay **off** |
| **C. Deploy** | PARTIAL | Web deployed; backend **`b642dd156`** verified via `/health` |
| **D. Production acceptance** | **NOT RUN** (app-level) | DB-only: member membership INSERT/UPDATE refused. Missing: anonymous `/api/sessions`, role changes, MCP stdio, retrieval +6m, watcher, regression |
| **E1–E5 follow-ups** | COMPLETE (code) | #402, #408–#410 + route audit / grants |
| **E. Vercel key** | BLOCKED | Operator |
| **E. Incident review** | NOT STARTED | — |
| **Product: member agent tool authority** | OPEN | Decision required |

**Release 1 gate:** **OPEN** (acceptance evidence missing).

Automated anonymous smoke: `scripts/verify-release1-production-smoke.py` → `docs/delivery/release1-production-smoke.json` (**PASS** for anon slice @ prod `b642dd156`, 2026-10-14).

---

## 3. Release 2

| Item | Status | PR / notes |
|------|--------|------------|
| Admin approvals bound to exact args, once, audited | COMPLETE (code) | #413 |
| Equivalent external sends same policy class | COMPLETE (code) | #412 |
| One policy check at provider boundary | **PARTIAL** | #414 **shadow** — logs, does not deny |
| No duplicate writes after 5xx | COMPLETE (code) | #415 |
| Background read-back updates chat | COMPLETE (code) | #416 |
| Stale run recovery | PARTIAL | #421 merged, feature **off**; ~19 stuck runs remain |
| Workflow approval bound to reviewed definition | **COMPLETE (code)** | Branch `cursor/full-release-implementation-6b92`: `workflow_approval_scope.py`, canvas gate |
| Stable logical action id + provider idempotency keys | **COMPLETE (code)** | `logical_action_id`, `write_invoke_idempotency` + migration `20261014100000`, `Idempotency-Key` on catalog HTTP |
| Unified lifecycle envelope + durable voice effects | **PARTIAL** | `lifecycle_envelope.py` persisted on task state; voice durable effects unchanged |
| Read-back by prioritized customer use | **PARTIAL** | Existing `write_success_verification` catalog; no new prioritization layer |
| Relay handler readiness + backlog dry run | **PARTIAL** | Handlers registered; `scripts/domain-event-relay-backlog-report.py` (read-only); relay **off**; prod backlog dry-run **NOT RUN** |
| Release 2 acceptance | NOT RUN | — |

---

## 4. Parallel track (conversation / intelligence / memory)

**NOT STARTED** — turn tracing + shared context artifact, P50/P95 latency, Railway LIVE/ranking flags proof, connector lineage enablement, two legacy external memories disposition, document lineage, resurfacing routes (snapshot, glossary, embeddings, tier0, voice prompt, summaries, history).

---

## 5. Release 3

| Item | Status | PR / notes |
|------|--------|------------|
| Signed webhooks, replay dedupe | COMPLETE (code) | #418 |
| SF/Segment/PagerDuty trigger constraints | COMPLETE | #418 + migration **070000** applied |
| HubSpot signature (full URI) | COMPLETE (code) | #417 — **real test delivery NOT RUN** |
| Encrypted signing secrets | COMPLETE (code) | 0 plaintext at seal time (operator) |
| Dedicated automation identity | PARTIAL | Runs credited to configuring admin |
| Freshservice → run → approval → read-back | COMPLETE (code) | #419 — **E2E BLOCKED** (no prod Freshservice connector) |
| Queue long work off inbound HTTP | **COMPLETE (code)** | `event_trigger_use_workflow_queue` + `try_enqueue_workflow_run` |
| Config UI, rotation, test-delivery status | **PARTIAL** | Workflow webhook config API + tests; Freshservice triggers panel; HubSpot test delivery **NOT RUN** |
| Assistant usage per turn | COMPLETE (code) | #411 — billing backfill is operator decision |
| Per-run time and cost | COMPLETE (code) | #420 + **080000** applied |
| model_calls `turn_id` populated | **COMPLETE (code)** | `bind_turn_attribution` on chat streaming path (branch) |
| Metering reconciliation, ROI caps, PSA baselines | NOT STARTED | — |
| Release 3 acceptance | NOT RUN | — |

---

## 6. Release 7 — model routing / economics

**NOT STARTED** (budget caps, adaptive routing gate, packaging from measured economics). Catalog/tier unit tests exist only.

---

## 7. Release 4 — MSP / external MCP

**PARTIAL (Option A scaffold)** — `parent_org_id` migration and `msp_org_context` + `MSP_PARENT_ORG_ENABLED`, with explicit child membership still required. The parent RLS path (`20261014110000`) was **withdrawn** and must not be applied. External MCP API, client switcher, acceptance **NOT STARTED**. See `docs/design/RELEASE_4_MSP_CLIENT_MODEL_OPTIONS.md`.

---

## 8. What blocks “plan complete”

1. **Deploy pair + Release 1 acceptance** — confirm Vercel SHA vs backend **`b642dd156`**, then run full matrix with test orgs (`docs/delivery/release1-production-acceptance.md`). Requires `SUPABASE_*` + mint script or human SSO.
2. **Operator decisions** — Vercel key presence, incident review, agent tool authority, billing missed turns, stuck-run cleanup (#421), write-authority enforce flip.
3. **Release 3 fixtures** — Freshservice connector + HubSpot test delivery.
4. **Remaining engineering (order)** — parallel intelligence track → Release 3 metering/ROI → HubSpot/Freshservice prod acceptance → Release 4 product (switcher, external MCP) → Release 7 routing. **Code train on branch `cursor/full-release-implementation-6b92`** covers approval scope, idempotency, lifecycle envelope, event queue, turn_id, MSP scaffold.

**Do not enable `DOMAIN_EVENT_RELAY_ENABLED` until handler idempotency and backlog dry run are approved.**
