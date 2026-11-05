# PR #605 — Gate 20: typed execution correlation, privacy review and individual retirement verdict

Date: 2026-11-05. **Status: code staged on draft PR; prior Gate 19 privacy suite passed; latest-head tests and production correlation acceptance pending. No production configuration change.**

## 1. Confirmed exact-head evidence from the previous gate

- Previous-head independent privacy workflow [42112109177](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42112109177), job `127542045039`: **5 passed / 1 pytest configuration warning**. The original off-by-default, minimum HMAC key, fixed-source-label, no-raw-ID and deterministic digest tests passed at prior commit `f067ed8177eb9a1b09b4b1526818fff39ea923b9`. This is a test certification, not approval for production data collection.
- Earlier source inventory workflow [42111333265](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42111333265) passed 6 tests, examined 12 owner sources/1,001 AST callsites and archived bounded JSON evidence.
- Railway production distributed traces queried read-only on 2026-11-05 for 20:27:34–21:27:34 UTC: **0 returned trace records**. This means the required execution-path spans have **not been observed**, not that the application was idle. Railway HTTP route observations from Gate 18 are sampled ingress only.

## 2. Implemented typed boundaries in this gate

`backend/app/services/runtime_execution_edge_telemetry.py` now provides an immutable `ExecutionCorrelation` wrapper with explicit `from_plan_id` and `from_run_id` constructors. Both are opt-in, deterministic HMAC-pseudonymized through `emit_handoff`; no raw identifier is written to this logger. The *same underlying ID* must be explicitly provided to produce the same digest; accidental joins across unrelated IDs are forbidden.

| Boundary | Instrumented code | Pseudonymous identity | Emitted event only if separately enabled | Evidence limit |
|---|---|---|---|---|
| Agent execution policy | `autonomous_execution_loop.decide_execution_loop` | `plan.plan_id` | `agent/selected/execution_plan` | Policy decision reached, **not tool execution** |
| Workflow result observation | `workflow_execution_strategy.apply_workflow_result_to_plan` | `plan.plan_id` | `workflow/observed/workflow_result` | Plan/observation boundary, **not external verification** |
| Connector result persisted to owned run | `ChatConnectorExecutionService._finalize_connector_outcome` | persisted `run_id` | `connector/observed/connector_result` | Result and run identity known; **not independently verified success** |
| Canonical terminal outcome fanout | `execution_outcome.finalize_execution_outcome` | `event.run_id` | `outcome/observed/terminal_fanout` | Outcome reached fanout; downstream writes can still fail individually |
| Play actioned result read model | same canonical outcome fanout, only if `play_actioned_recorded` | `event.run_id` | `play/observed/play_actioned` | Play result was recorded, **not full independent play correctness** |
| Durable event consumer handler | `DomainEventRelay._dispatch` | outbox `event.id` | `event_consumer/started|completed|failed` | Handler-local event ID, **not implicitly a workflow/run ID** |

### Explicit correlation gap

Agent and workflow records can be joined **only** when they share a genuine plan ID. Connector, outcome and play records can be joined **only** when they share the real persisted run ID. Event outbox records are HMACed from their own event primary key; their relationship to an upstream execution **has not been proven or propagated in the emitted contract**. No telemetry dashboard may claim one complete ingress→agent→connector→workflow→outbox chain from this release alone. The source tool registry, Next.js client, remote model, provider write and Temporal execution paths still lack end-to-end correlated execution events.

## 3. Privacy controls and approval packet (not yet approved)

**Current status: PROD COLLECTION OFF**. The code only emits when `PR605_EXECUTION_EDGE_TELEMETRY_ENABLED=true` *and* a dedicated `PR605_EXECUTION_EDGE_HMAC_KEY` has at least 32 characters. Neither variable was changed on Railway or Vercel by this work. Existing token/transcript/customer/payload values must never become attributes.

Production enablement requires separate security/privacy/operations review covering: (1) purpose limitation and documented acceptable identifiers; (2) key generation in approved secrets manager, rotation/TTL and cross-service scope; (3) log sink access control, tenancy and retention; (4) sampling and rate caps; (5) omission of plaintext prompts, message payloads, tokens, provider outputs and user IDs; (6) failure-mode and no-blocking-path performance test; (7) collection notice/consent where applicable; (8) explicit rollback/disable; (9) control that traces are queryable by non-sensitive correlation digest only; (10) assurance that aggregate event IDs aren't falsely treated as run IDs.

Once approved, deploy to an authorized controlled environment, execute matched read-only/approval/write-denial/revocation/crash/restart fixtures, and inspect actual timestamped per-span results. Post-merge production paid/live voice acceptance remains governed by the existing release sequence.

## 4. Automated checks added

`backend/tests/services/test_runtime_execution_edge_telemetry.py` now includes typed plan/run identity tests. Assert: five supported handoffs produce two distinct groups (agent+workflow under same plan ID; connector+outcome+play under same run ID), each group yields stable HMAC digests, groups do not alias, raw IDs never appear in logs, and absent IDs cannot emit. Prior five original tests passed; two added tests require **new exact-head CI certification**.

Independent workflow `.github/workflows/pr605-runtime-edge-contract.yml` triggers on all modified boundary modules and executes isolated privacy tests plus Python syntax compile, without live providers or DB reads.

## 5. Individual retirement evaluations

| Candidate | Replacement coverage demonstrated | Decision |
|---|---|---|
| Classical ReAct and alternative LIVE tool-loop paths | No runtime same-authority/SSE/governed write parity or authenticated request traces | **NOT APPROVED** |
| Voice HTTP, Pipecat WS and alternative PCM renderer | No correlated acoustic/transport client acceptance | **NOT APPROVED** |
| Agent/play/workflow competing dispatchers | Only partial policy/observation/fanout correlation, no live consumer replacement proof | **NOT APPROVED** |
| Connector provider routers and approval paths | Result identity boundary only, not verified tenant scopes/auth/fences end-to-end | **NOT APPROVED** |
| workflow_runs vs runs and old status projection | Canonical status v2 staged; production DB identity, consumers and history remain unapproved | **NOT APPROVED** |
| Domain event relay / outbox | Critical at-least-once, retry and handler semantics must be preserved | **KEEP, NO RETIREMENT** |
| Temporal/Redis/Railway alternate frontend | Service ownership/workers/cost/rollback not sufficiently certified | **NOT APPROVED** |

**Destructive retirement approvals: zero.** Keep essential resilience and write-fence contracts.

## 6. Final gate requirements

1. Inspect new exact-head Gate 20 privacy CI, integrated full CI and dedicated route/PG certification. Repair any actual failures; no skipped test counted as pass.
2. Complete shared typed root→child correlation across remaining agent/play/workflow/connector/event relationships using documented, authenticated IDs and existing durable fields; ensure unrelated IDs never coalesce. Add controlled no-provider replay/cancellation/governed write tests.
3. Obtain review for any actual telemetry enablement, and then inspect real privacy-safe traces in the approved environment.
4. Attest production Supabase project identity through the non-secret ref of the deployed Railway configuration (do not infer based on database content); historical reconciliation separately authorized.
5. Certify each retirement candidate against observed production reachability, complete consumer migration, equivalent security and behavior, rollback and independent reviewer approval.

**Gate 20 remains OPEN.** This document certifies completed source changes and previous-head CI evidence only, not live execution completeness or production privacy approval. PR #605 remains draft/unmerged/undeployed; no historical data, schema or production configuration was modified.
