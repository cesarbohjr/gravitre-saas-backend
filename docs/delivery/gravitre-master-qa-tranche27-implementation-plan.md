> **2026-11-07 priority override — audit remediation first.** This document's original P0–P5 QA build sequence is subordinate to the full-platform audit-to-remediation program in [master-qa-remediation-program.md](master-qa-remediation-program.md). Its [43-item v2 ledger](master-qa-remediation-register.v2.json) is the release-scope source of truth for engineering defects, missing infrastructure, cross-system wiring and consumer proof. Every ECO/DEC/P27 finding remains uncertified until a named owner records real source-to-runtime evidence, targeted repair, negative and downstream tests, exact-SHA CI, rollback and any required live acceptance. PR #610 **alone** owns Voice 3.0 V0–V7 implementation; PR #611 imports the results into QA30 and owns cross-platform ingress wiring/release evidence. A green Master QA synthetic job verifies only its named tests, never overall audit completion. New testing infrastructure is not required and no paid staging is authorized.

# Gravitre Master QA — Tranche 27 integrated implementation and governance plan

## Resume review — 2026-11-08, baseline PR #611 `60c89ba865a`

This checkpoint reconciles the original **Complete Six-Phase Engineering,
Multimodal Parity and End-to-End Acceptance Plan** (2026-10-24), PR #610 at
`668ebc48a175202f25c1e6220dedace4490b8013`, this plan, the remediation program,
the autonomous business mandate and the canonical entrypoint trace. It does
not replace any of those contracts or create another execution authority.

### Implemented versus certified

| Scope | Branch implementation reviewed | Remaining proof / work |
| --- | --- | --- |
| Foundation and release truth | Workflow source audit, deterministic fixtures, 43-finding guard, 28-edge preflight, QA00–90 manifest | Operational workflow dispositions, runtime caller census and per-finding closure. Guard still reports 43 open / 30 P0 / zero certified closures. |
| Canonical goal understanding | `GoalService.analyze_for_org`, tenant-connected evidence requirements, explicit unverified model fallback | Model-intent quality, authorized retrieval/provenance and executable all-domain coverage. Understanding is not execution certification. |
| Goal → canvas | Bounded read-only sales recipe uses existing builder/graph/runtime; from-goal route persists graph | Other domains remain model-suggested drafts; authenticated canvas round-trip and provider results remain unverified. |
| LIVE/classical/ReAct | Structured fallback authority, one-shot tool-choice handoff, typed/voice contract tests | Current-turn ownership repair below; actual ingress traces, streamed terminal-result parity and approval/revocation races. |
| Agent → Play → workflow → outcome | Joined PostgreSQL tests, canonical run receipt requirement, blocked/partial objective truth | New exact-head PostgreSQL CI; live provider readback and deployed downstream/UI acceptance. |
| Durability | SQL leases/checkpoints, outbox consumers, isolated process recovery tests and default-off supervisor | Existing Railway child-only recovery and API continuity remain NOT RUN. |
| Voice #610 V0–V7 | Specification only; #611 tests shared reasoning interfaces | V0 baseline, V1 reproduction then V2 turn commit, V3 honesty, V4 PCM, V5 comparison, V6 integration, V7 live/device/human acceptance. |
| Original six-phase obligations | Preserved, not discharged by the newer goal mandate | All 26 model readiness states; seven-capability positive/negative invocation **and consumption**; four modalities; E01–E24; dialogue/expressiveness; provider compatibility/A-B; consented verified learning and repeat-turn measurement. |
| Forecasting and monitoring | Existing mandate defines required outcomes | Inventory and extend existing metrics/forecast/replan/scheduler owners; calibration, insufficient-data abstention, opt-in monitoring and budget controls remain uncertified. |

### Current corrective work

1. **Handoff lifetime:** `consume_handoff()` exhausted only ContextVars while
   `arm_from_task_state()` retained the original choice/queue in persistable
   task state. Rehydration could re-arm consumed choices; an interrupted
   evidence queue could reject a new choice. Transfer the queue out of task
   state at arming, preserving canonical approval/execution state. Five
   deterministic regressions cover serialized retry, interrupted queue, ordered
   execution, cancellation before dispatch and overlapping turn isolation.
   These tests do not claim provider exactly-once semantics or fix arbitrary
   historical copies saved before the transfer.
2. **Non-sales response failure:** general from-goal creation called removed
   `GoalAnalysis.as_dict()` after persistence. Use its canonical Pydantic
   `model_dump()`, as the sales path already does. Preserve the analyzed object
   through draft generation; extend the route regression over support,
   finance, operations, HR and engineering. They remain explicitly
   `NOT_CERTIFIED` / `NOT_MEASURED`, with no automatic execution.
   Baseline [Master QA run 42545727289](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42545727289)
   independently reproduced this same failure (171 passed, one failed);
   its PostgreSQL step was consequently not run.

Local targeted validation: **135 passed, zero skips**, including the new
handoff and expanded non-sales cases, goal compilation, objective execution
truth, typed/voice parity, fallback and release/remediation/preflight tests.
The exact existing Master QA runtime guard command also passes locally:
**181 passed, zero skips**. Stored-dict lint: **2 passed**. Local PostgreSQL
is **NOT RUN**: binaries are absent and package installation cannot change
UID/groups in this environment. The existing disposable PostgreSQL Actions
lane remains the execution surface. Exact-head full CI, PostgreSQL, deployed
acceptance and real voice/provider proof remain distinct gates.

### Next dependency order

1. Restore exact-head Master QA/general CI; execute the joined disposable
   PostgreSQL lane and investigate failures before widening feature scope.
2. Finish canonical ingress and execution authority proof: actual
   chat/voice/agent/Play/builder paths; one terminal result, cancellation,
   approval/revocation, missing scope, replay and durable downstream outcome.
   Runtime correlation remains subject to the existing issue #607 scope.
3. Extend the current goal/capability/Play/builder owners for further domains
   using actual authorized evidence and schemas; preserve all missing-data and
   unsupported-action blocks. Finish the sales reference journey's independent
   readback and baseline/follow-up metrics.
4. Preserve the original model/intelligence inventory and E01–E24 obligations;
   verify relevant capability consumption, all four modalities and consented
   learning. Do not infer readiness from catalog entries or CI job titles.
5. Extend existing forecasting, recommendation and goal monitoring paths only
   after evidence/metric semantics are proven; measure accuracy, calibration,
   latency and cost before optimization.
6. Complete #610 V0–V7 in its owning PR and ingest QA30 evidence here; finish
   browser/mobile/tenant/billing/recovery coverage, operational workflow audit,
   per-finding certification and authorized deployment/rollback/live acceptance.

No merge, deployment, production migration, provider write, telemetry
activation, extra paid service or certified finding closure is part of this
checkpoint.

**Status:** ENGINEERING PLAN / NOT CERTIFIED. **Date:** 2026-11-07. **Base snapshot:** `main@cf8b95d25a6a70aa5db3b8eef103e6f86786b773`.
**Owning implementation branch:** `feat/master-qa-tranche27-orchestration` (new, from main).
**Companion voice branch:** `feat/qa-master-voice-parity-gates`, PR #610 (draft; authored separately, not yet integrated).
**Historical branches:** PR #605 merged at `cf8b95d25`; PR #608 merged and was connector overlay UI (NOT the QA implementation). Legacy branch `feat/gravitre-master-qa-automation` was 0 ahead / 16 behind main at discovery; do not force-update, delete, or mistake it for implementation.
**Approvals:** Issue #607 is the EXISTING Gate 24 Security/Privacy + Operations runtime-correlation approval ledger; it must retain its narrow scope. PR-specific engineering/release decisions belong in linked PR comments. Do not convert #607 into an implementation PR.

## 0. Context preservation — what was agreed, what exists, what remains

The agreed Master QA objective is an **ongoing synthetic-first engineering regression and certification system**, not simply a document or a successful historical CI run. Every engineering fix from Tranche 27 must acquire a reproducible regression scenario, assigned code owner, automated gate, and evidence ledger. It covers chat/model routing, live-feeling duplex voice, agent/tool initiative, connectors, Plays, workflows, real governed execution, durable state/outbox, billing, auth/tenancy, browser UX, operations, and cross-surface parity. It should safely test failures and fixes as they are engineered, with cheap deterministic local fakes and disposable services first, then separately approved live acceptance. Measure user-observable ChatGPT-class behavior without claiming access to proprietary competitor internals.

**Original source of truth:** `docs/delivery/pr605-automated-quality-acceptance-program.md` (already on main; its QA 00–90 specification remains authoritative).
**Voice companion:** `docs/delivery/gravitre-voice-3-master-engineering-qa-plan.md` (currently only on PR #610). Integrate its V0–V7 gates, Deepgram/ElevenLabs/Pipecat timing and turn-arbiter cases without prematurely claiming the document merged.
**PR #605:** modernization, versioned run-status contract, registered-route inventory, owner boundaries, isolated PostgreSQL/outbox, connector governance, billing isolated acceptance: 5 required checks + 17 specialized workflows and 7/7 billing E2E passed on final PR head. This is proven historical **pre-merge** evidence, not an evergreen Master QA system or production certification.
**Issue #607:** approval register for privacy-safe HMAC/runtime correlation. Do not activate production telemetry or broaden its approval by implication.
**Reality of main:** 92 `.github/workflows/*.yml` files were enumerated on `main@cf8b95d25`. Many are manual, live, production, path-filtered, synthetic or specialized; inventory them individually before deciding to keep/consolidate/retire. `main` is protected under the owner's solo-maintainer policy, which does not mandate an independent reviewer; keep current rules unchanged unless separately approved.

### Previously communicated findings — preserved for all linked PRs

1. Original blueprint: QA 00 fast contracts, QA 10 synthetic integration/durability, QA 20 agent/Plays/enterprise journeys, QA 30 chat/model/voice, QA 40 browser/API, QA 50 extended reliability, QA 90 exact-head evidence.
2. Existing #605 specialized CI and genuine seven-test billing run are valuable foundation, not proof of end-to-end Master QA coverage. The workflow inventory, synthetic enterprise test factory, unified orchestration and Tranche 27 finding→test→fix→evidence mapping were **not verified complete**.
3. #610 is a new *draft voice specification*; its synthetic turn, speech, action-honesty and acoustic tests are not yet certified. The stale original QA branch has no unique implementation.
4. Preserve all existing passing checks and release holds. Do not lower test thresholds, treat skipped as pass, enable live providers, introduce paid infrastructure, deploy, or merge to manufacture certification.
5. P27-01–08 production journeys remain **NOT RUN / NOT CERTIFIED** until separately approved release, exact deployed SHAs, tested operator/window, privacy approvals and user acoustic sign-off.

## 1. How I recommend we resume — sequenced implementation

### P0 — Establish current-main baseline and workflow disposition before changes
- Take a machine-readable exact-SHA inventory of all 92 workflows (re-enumerate if main moves) with name/path, event triggers, concurrency, required-check name, jobs, `workflow_call` callers, branch/path filters, secrets/permissions, live or paid side-effects, deployment hooks, average runtime/last meaningful execution (when observable), retention and cost exposure. Explicitly identify manual live/prod-only flows. Save an inventory JSON and human-readable KEEP / CONSOLIDATE / RETIRE / INVESTIGATE ledger with reason and owner.
- Inventory current tests, routing/ownership artifacts, status contract, database migrations, Supabase/Stripe acceptance, existing synthetic fixtures, Playwright, voice simulations and delegated provider boundaries. Map to 7 lanes; mark missing/unexercised surfaces UNKNOWN/NOT_RUN.
- Verify current `main`, all open PR heads (especially #610), branch protections and deployment holds. Avoid modifying current CI triggers or status names in P0.
- Publish baseline execution time/minutes/artifact storage with honest cost exposure, not an ungrounded zero-cost guarantee.

**Exit:** Reviewed inventory and coverage map; no retired workflow or modified required check, no additional infrastructure.

### P1 — Reusable synthetic isolation foundation
- Implement versioned deterministic fixture factories for disposable tenants/orgs, RBAC, approvals, conversations, plans/agents, runs/outbox, subscriptions/entitlements, and authorized user roles; cleanup and random ID isolation.
- Use per-run throwaway PostgreSQL (and Redis only when tests genuinely require it), test clock, predictable scheduler and seed. Never connect synthetic tests to production database, Stripe live, customer tenants or vendor tokens. Network egress deny-by-default with explicit loopback/local-fake allowlist; prove negative-path failure.
- Deterministic simulated native/Nango OAuth, CRM, email, support, ads, analytics, Stripe webhook signing, Deepgram STT events, ElevenLabs chunk streams, LLM/tool replies. Explicitly label `SIMULATED` vs `SANDBOX_LIVE` vs `PRODUCTION_LIVE`.
- Safely reuse the pre-existing dedicated Supabase acceptance project when *manually* running isolated billing tests; prefer offline fixtures for PR CI. Do not provision paid permanent staging or leak credentials. Preserve schema target allowlist/test-mode guards.

**Exit:** reproducible seeds, isolated persistence, denied external writes, verified teardown and fast contract suite.

### P2 — Tranche 27 defect-to-test coverage register
- Convert each open Gate 26/Tranche 27 audit item (and each newly confirmed incident) into a stable record: `finding_id`, severity, reproduction, affected entrypoint/owner, existing regression IDs, missing proof, expected durable behavior, implementing commit, gate, artifact and state (`NOT_RUN | BLOCKED | FAIL | PASS`).
- Include actual agent→Play→workflow→connector→outbox→consumer scenarios; authorization/approval/deny/revoke, tenant boundaries, idempotent retries, provider timeout, stale/duplicate callbacks, worker crash/restart, cancellation and durable recovery, cross-surface status v2.
- Validate **persisted effects and downstream consumers** rather than only generated text or mock invocations. Zero unauthorized writes, cross-tenant leaks, invented completion or silent dropped outcomes.

**Exit:** every Tranche 27 finding linked to at least one planned or implemented regression, explicit unmapped blockers.

### P3 — Chat, voice and enterprise quality lanes
- Chat/agents: direct responses, long-context retention, correct model/provider routing, proactive but authorized connector discovery, task selection and multi-step execution; record TTFT, tool precision, verified completion and false completion.
- Voice: import PR #610's V0–V7 test definitions *after reviewing its exact head*. P0 turn gate: 400/800/1200 ms pauses, correction, eager-EOT→TurnResumed, duplicated final, no premature audible output. Dialogue: no unsolicited 'let me check', relevant tool initiation, approvals and outcomes. Audio: deterministic PCM starvation, chunk jitter, ducking, replay suppression, reconnection, barge-in, epoch cancellation. Mirror committed text/voice semantics.
- Web/API: Playwright isolated browser, login, billing, approval UX, accessible and mobile interaction; API schema/route drift. Include complete pricing catalog coverage as a separate bounded follow-up, not claim current Node monthly test covers every plan.
- Benchmarks compare observed experience and cost/latency baselines, not proprietary internal parity. Stochastic evals require calibrated human-reviewed datasets and budget approval; correctness safety invariants remain deterministic.

**Exit:** scripted reproducibility, quality rubric, measured baselines; **physical microphone, subjective voice naturalness and paid provider behavior remain unverified**.

### P4 — Master QA orchestration, without breaking main
- Introduce **one clear entrypoint** with readable reusable lanes, keeping required status contexts stable:
  - `QA 00 — Change Scope & Contract Checks`
  - `QA 10 — Synthetic Integration & Data Durability`
  - `QA 20 — Agent, Play & Enterprise Workflow Acceptance`
  - `QA 30 — Chat, Model & Voice Quality`
  - `QA 40 — Browser & API End-to-End`
  - `QA 50 — Extended Reliability` (manual/nightly ONLY with owner-approved Actions budget)
  - `QA 90 — Master Release Evidence`
- Start as an **additive** PR-only workflow with bounded timeouts, no vendor secrets, least permissions, explicit scenario manifests, deterministic caches and small artifact retention. Avoid duplicate costly full-run work: retire old paths only after parity/consumers/branch-protection dependencies are proven and explicitly reviewed.
- QA 90 produces schema-validated per-SHA evidence: workflow IDs, scenario IDs, fixture digests, environment, all `PASS/FAIL/BLOCKED/NOT_RUN`, p50/p95, cost/run, provenance (`synthetic/sandbox/live`), unresolved regressions, review and go/no-go recommendation. Fail closed on required missing jobs, canceled/skipped jobs and stale SHA. Do not create a self-grading green master badge if dependent checks are missing.

**Exit:** repeatable PR execution, independent required checks preserved, lower duplicate cost demonstrated, strict fail-closed evidence.

### P5 — Controlled later acceptance; NOT covered by synthetic green
- After separate release/owner approvals, complete Tranche 27 P27-01–08 on actual deployed SHAs with controlled synthetic accounts and precise downstream effect checks. Issue #607 holds independent Security/Privacy and Ops decisions for telemetry only; do not equate its existence with approval.
- Voice physical iOS Safari + desktop, ~20-minute real dialogue, deliberate interruptions, audio quality and action follow-through; final user sign-off is distinct from automated simulation.
- Record rollback exercise plan, operator and window; preserve currently disabled Railway Git autodeploy, Vercel Production Git restrictions and Railway deploy workflow until specifically approved restoration.

**Exit:** labeled production evidence and separate authorization; no implicit deployment.

## 2. Branch and PR responsibility / cross-links

| Artifact | Responsibility | State at kickoff |
| --- | --- | --- |
| `main` | Source of truth; protected / #605 merged | Snapshot `cf8b95d25` |
| `feat/master-qa-tranche27-orchestration` | Master QA baseline, fixtures, journey matrix, QA 00–90 CI, evidence; this document | New implementation branch |
| `feat/qa-master-voice-parity-gates`, PR #610 | Detailed voice 3.0 V0–V7 engineering/QA; incorporate via review into QA 30 | Existing draft; do not rewrite or merge automatically |
| `feat/gravitre-master-qa-automation` | Historical placeholder; **not** implementation owner | 0 ahead / 16 behind; keep for traceability, no force-push |
| PR #605 | Merged modernization / billing precedent | Closed/merged; reference and comment only |
| PR #608 | Merged connector overlay UI | Not a Master QA PR |
| Issue #607 | Security/Privacy + Operations runtime-correlation approvals | Open; retain existing scope |

Do not manufacture a full QA system from just this document. Planned tasks must become real commits/tests, and new commits must get new exact-head certification. If `main` changes, reconcile content-aware and rerun every affected gate, without force push.

## 3. Immediate implementation milestones (first engineering loop)

1. P0-A: `master-qa-workflow-inventory.json` and `master-qa-disposition.md` from all 92 workflows, without changing their behavior.
2. P0-B: existing tests to QA lanes / Tranche 27 coverage matrix with real file/test/workflow references, defect IDs and `NOT_RUN` for gaps.
3. P1-A: network-denied deterministic synthetic fixture starter + tests, disposable Postgres harness reuse, cleanup and failure-state coverage.
4. P2-A: one full local agent→tool→outbox→consumer persisted-effect acceptance and a denied-write/revocation pair, all tenant-isolated.
5. P3-A: voice turn-commit and PCM fault fixtures from PR #610, no paid providers.
6. P4-A: initial additive master workflow with 00/10/20/30/40/90 manifest and fail-closed evidence; 50 manual-only.
7. Inspect actual runs, repair confirmed defects, record each exact SHA and regression before extending coverage.

## 4. Rules of engagement

- **No merge, main write, production deploy, migration, telemetry enablement, legacy deletion, branch protection modification, account/key change, paid provider test, or paid resource provisioning** under this plan without separately explicit approval.
- Synthetic success is NOT production readiness; no fabricated result or unsupported ChatGPT-class parity claim.
- No destructive workflow consolidation until caller/dependency and required-check audit is certified.
- Preserve timeouts, zero-retry behavior and assertions unless evidence warrants an independently reviewed improvement.
- Maintain links from this plan in the new Master QA PR, voice PR #610, historical #605, and issue #607; each link must distinguish existing completed evidence from pending implementation.
