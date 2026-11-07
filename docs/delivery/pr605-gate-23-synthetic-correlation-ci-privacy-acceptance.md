# PR #605 — Gate 23: full-CI certification and offline correlation acceptance

Date: 2026-11-05. **Status: independent privacy gate certified at previous head; full integrated CI not yet certified; offline synthetic test staged; live privacy approval NOT GRANTED.**

## 1. Exact prior-head CI evidence

On PR SHA `2e89da94ee181e34bc716c9103a1fa6190cf2e48`:
- Privacy workflow [42118274668](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42118274668) **SUCCESS**: 13 focused tests passed and one pre-existing pytest configuration warning, job `127563594800`.
- Independent registered-route, ownership inventory, run-status PostgreSQL, Supabase migration safety, outcome contract, connector governance, and relevant frontend/voice checks reported success.
- Integrated [full CI 42118274581](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42118274581) was **IN PROGRESS**, not passed, at inspection. Its `Web (lint + typecheck + build)`, `Dependency audit`, and `Shared runtime text/voice gate` jobs were successful, while `Backend (pytest)` remained in progress. A partial set of passing jobs cannot certify the full workflow.

## 2. New offline synthetic acceptance preflight

Added `test_synthetic_end_to_end_correlation_graph_without_customer_data` to `backend/tests/services/test_runtime_execution_edge_telemetry.py`. It deliberately generates synthetic plan/run/outbox IDs and a test-only HMAC key, then invokes only the pure privacy logger functions. It verifies:
- agent↔workflow plan digest equality;
- plan→run bridge from a named `orchestration_step` source;
- connector↔outcome↔play run digest equality;
- run→outbox bridge for an `execution.outcome_finalized` / `workflow_run` trigger contract;
- event-consumer matching to the event digest;
- distinct plan/run/outbox identities remain distinct;
- unrecognized connector events don't masquerade as workflow-run outbox linkage;
- raw synthetic IDs and key do not enter logs.

**Critical scope note:** This is a unit-level *synthetic lineage contract preflight*, not an end-to-end running application test and absolutely not live production execution trace evidence. It does not test HTTP authorization, queued workers, Postgres trigger execution, provider observation, consent, write approval, cancel/revoke, tenant isolation, real consumer side effects, latency or audio. The previous 13-test pass does not certify the **new 14-test suite**. A new exact-head privacy workflow and full CI must pass.

## 3. Production privacy approval and live tracing

**NOT APPROVED.** The existing Gate 22 approval packet still needs named accountable Security/Privacy and Operations sign-off for log purposes/data fields, dedicated HMAC secret handling, access/tenant isolation, sample rate and cost, retention/deletion, consent/notice where applicable, and a measured rollback/disable plan.

No production variables were changed. The production deployment does not contain the newly staged branch code. Prior Railway read-only distributed trace observations returned zero spans in inspected periods; that is a telemetry gap rather than an assertion of no traffic. Do not enable `PR605_EXECUTION_EDGE_TELEMETRY_ENABLED` or generate a production HMAC key without explicit approval.

## 4. Individual legacy retirement decisions

| Candidate | Latest acceptable evidence | Decision |
|---|---|---|
| Classical ReAct / LIVE tool SSE fallthrough | No matched prod execution parity, approvals, cancellation, verified tool result | BLOCKED |
| Voice alternatives / PCM paths | No real production acoustic/transport equivalence | BLOCKED |
| Agent/play/workflow dispatchers | Synthetic linkage preflight only, no real consumer/worker trace | BLOCKED |
| Connector catalog and executor | No end-to-end authorized provider observation and write fence comparison | KEEP; RETIRE BLOCKED |
| workflow_runs/run projections | Trigger/source link verified; actual DB identity/read-model cutover not proven | BLOCKED |
| Outbox/relay | Durable event delivery and replay required | KEEP; NO RETIREMENT |
| Temporal, Redis and alternate frontend | Live consumer/queue/resource ownership incomplete | BLOCKED |

**Authorized destructive retirement count: ZERO.**

## 5. Release next actions

1. Certify all applicable workflows against a **single final commit SHA**, including the new 14-test privacy suite, backend pytest, web build, route inventory, DB migration/status checks, connector governance and integrated full CI. Diagnose actual logs for any failing test, rerun after correction; cancelled/queued/pending are not passes.
2. Obtain explicit privacy/security/operations authorization before staging real runtime correlation collection. Prefer a no-customer-data acceptance environment and synthetic tenant/workflow fixtures. Capture and inspect actual trace digests and durable outcome/consumer events, including denied/approved writes, revocation, restart/idempotency, failure, multi-tenant isolation and rollback.
3. Verify the target environment's Supabase project identity using an approved **nonsecret project ref**, without extracting live credentials.
4. Update retirement register per candidate with authenticated real caller observations, replacement equivalence, safety tests, rollback and reviewer signoff.

**No production telemetry activation, merge, deployment, database or historical record modification, or legacy retirement performed. PR remains draft.**
