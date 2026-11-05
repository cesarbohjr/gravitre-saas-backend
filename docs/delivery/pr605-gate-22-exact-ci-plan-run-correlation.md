# PR #605 — Gate 22: exact-head CI certification and verified orchestration plan/run correlation

Date: 2026-11-05. **Status: Gate 21 privacy tests certified; new Gate 22 code pending exact-head CI; full CI not yet certified; production tracing remains OFF and not privacy-approved.**

## 1. CI evidence and blocking condition

- On prior exact PR SHA `78fbd891bb615f8a3737204600d801d54ccbe5ac`, [privacy workflow 42113881101](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42113881101) completed **SUCCESS**, job `127548252456`, with **10 passed, 1 pytest configuration warning**. The warning was `Unknown config option: asyncio_mode` because the isolated workflow installs only pytest; not evidence of a test skip.
- The same prior SHA had successful independent route, ownership, PostgreSQL status, migration safety, connector governance and other scoped acceptance workflows, as listed by GitHub Actions.
- The prior SHA's [integrated full CI 42113880911](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42113880911) was **PENDING**, with no job details, at the time inspected. **No integrated full-CI pass**; independent green gates do not substitute.
- Gate 22 changes to multiple code/tests/workflow files require newly completed runs on final exact SHA; a queue/pending/cancelled run is not a pass. No runner or CI concurrency changes are authorized by this checkpoint.

## 2. Verified root→plan→run evidence and implementation

The prior structure already passed a plan ID from `chat_orchestration_service._execute_current_step` into `dispatch_execution_step` when `task_state.execution_plan` is available; the same handler obtains `params.orchestration_run_id` and calls `sync_orchestration_step` on that persisted run. Gate 22 adds an opt-in, source-allowlisted **plan→run** linkage at precisely this joint-owner boundary, only if the real `ExecutionPlan` was restored and the run ID exists. It explicitly **does not** use the synthetic `step_id` fallback as the identity of a real execution plan.

- `runtime_execution_edge_telemetry.emit_plan_run_link` accepts the two existing identities only through the named `orchestration_step` source, requires the opt-in telemetry flag, HMAC secret and UUID-shaped run ID, and emits two shortened HMAC-SHA256 digests. It never logs raw plan/run values or arbitrary labels.
- `chat_orchestration_service._execute_current_step` calls this helper before updating the persisted orchestration step when both genuine identities exist. This is observation metadata; it does not alter connector authorization, execution, write approval or run persistence semantics.
- The existing `execution.outcome_finalized` workflow-run outbox trigger (migration `20261012024141_domain_event_outbox.sql`) provides the separately proven **run→outbox event** link from Gate 21.
- `runtime_execution_edge_telemetry.emit_handoff` now restricts `source` to a **closed set of known code labels**, instead of accepting arbitrary well-formed alphanumeric strings. This tightens metadata privacy against accidental dynamic text or identifier leakage.
- Privacy suite adds three tests for real plan/run HMAC join, malformed/untrusted context rejection and previously accepted but unregistered labels (13 focused tests total expected; must **confirm actual CI result**). Source code is no substitute for a passing job.

### Precisely demonstrated linkage, and what remains unknown

`autonomous agent execution decision (plan_id)` → `workflow observation (same plan_id)`: bounded typed correlation at those paths.

`chat orchestration execution plan (plan_id)` → `persisted orchestration run (orchestration_run_id)`: **source-bound call-site association**, now observable pseudonymously when explicitly enabled.

`connector result (owned run_id)` → `canonical outcome / play actioned read model (run_id)`: bounded shared identity for that connector-created run.

`workflow run (run_id)` → `execution.outcome_finalized outbox (aggregate_id=run_id)` → `relay event (outbox primary key)`: trigger-verified typed link.

**Not yet proved:** a single request traversing all four chains, an arbitrary agent plan equating to an orchestration plan, arbitrary connector-owned run being the same as orchestration run, uncorrelated Temporal tasks, complete provider success, consumer side effects, voice STT→LLM→TTS→playback, or all frontend callers. No fabricated joins or claimed production coverage.

## 3. Production trace and privacy approval state

Read-only Railway production trace queries had **zero returned distributed spans** in the inspected windows. Production variable-name inventory previously showed no `PR605_EXECUTION_EDGE_*` controls; values remain redacted. New telemetry remains disabled by default, and the newly committed code is not deployed to production.

**Production approval packet — still requires an authorized owner to sign off:**
1. Security/privacy review of purpose, legal basis/notice if required, data dictionary and per-tenant minimization.
2. New independent secret provisioned through approved Railway secrets, secret access control, rotation/rollback and audit trail; HMAC digest correlation scope and reidentification risks.
3. Sink access restrictions, short documented retention, deletion practice, aggregation/sampling thresholds, cost budget, and malicious-input/source allowlist review.
4. Acceptance-only synthetic tests: successful read, denied write, approval, revocation, cancellation, idempotent replay, outbox retry/consumer failure and multi-tenant separation. Compare actual span IDs and verified outcomes, not timings alone.
5. Explicit deployment/production change authorization and a kill switch; verify configuration and deployment SHA before read-only observation. **No production config updates, paid provider calls or deployment were made in this gate.**

Until authorization is recorded, no production telemetry collection should be enabled or described as complete.

## 4. Retirement candidate decision matrix

| Candidate | Evidence after Gate 22 | Verdict |
|---|---|---|
| ReAct / classical fallback | No measured end-to-end live replacement and authorized tool SSE/write parity | BLOCKED |
| Voice HTTP, WS and dual PCM renderer | No real-session acoustic and client fallback traces | BLOCKED |
| Agent/play/workflow engine consolidation | Joint plan/run callsite only for a bounded orchestration branch; no full runtime coverage | BLOCKED |
| Connector discovery/execution | Existing outcome boundary and run ID; not full tenant/provider read/write success and replay | BLOCKED |
| Workflow/run mirror and status v2 | Outbox link proven in source, production DB identity/consumer cutover unverified | BLOCKED |
| Outbox/relay | Mandatory durable event and at-least-once consumer semantics | KEEP, NO RETIREMENT |
| Redis, Temporal, alternate frontend | Active workload ownership, external dependencies, cost and rollback unresolved | BLOCKED |

**Approved destructive retirement candidates: ZERO.**

## 5. Required next gates

1. Let the final SHA's privacy, route, dependency, database, governance and **full integrated CI** complete; inspect logs/artifacts and fix real failures, then rerun. A prior SHA's passes are insufficient.
2. In a separately authorized, privacy-reviewed test environment, exercise correlated root→plan→run→outbox→consumer fixtures end-to-end including tenant isolation, approval/revocation, cancellation, restart/replay and provider-confirmed terminal outcomes. Do not enable production collection beforehand.
3. Attest the production Railway Supabase project ref nonsecretly, compare deployed commit/config metadata and then investigate actual runtime consumer effects, avoiding live secret exposure or unapproved schema/historical edits.
4. Individually certify any retirement only after all active callers, equivalent capability, security/write-fence regression, rollback and signoff are documented.

**PR remains draft, unmerged, undeployed. No schema migration, data reconciliation, provider consent action, or production trace activation occurred.**
