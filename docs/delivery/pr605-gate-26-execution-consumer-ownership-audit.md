# PR #605 — Gate 26 execution and consumer ownership audit, tranche 1

Date: 2026-11-05. **Source inspection only; not production execution certification.** Additive to governing modernization plan, production gap register, retirement register, and Gate 26 continuation.

## Inspected exact branch files
Branch `feat/gravitre-unified-ecosystem-modernization`:
- `backend/app/services/chat_orchestration_service.py`: `ChatOrchestrationService._start_execution` persists an orchestration run and stores `orchestration_run_id` in parameters; `_execute_current_step` reads the run ID and an execution plan and conditionally emits `emit_plan_run_link` when both exist. This is a real source-backed plan/run handoff; no evidence here that every route uses it.
- `backend/app/services/chat_connector_execution_service.py`: `ChatConnectorExecutionService` includes execution, write claim/reconciliation, canonical write outcome persistence and `_finalize_connector_outcome` returning a run ID when created. Investigate all branches for write authorization, uncertain results, replay and idempotency before consolidation.
- `backend/app/services/execution_outcome.py`: `ExecutionOutcomeEvent` carries a run ID; `_persist_run` persists canonical terminal run status; source header explicitly describes `workflow_runs` and mirrored `runs/run_steps`. `_write_audit`, `_emit_notification` and `_record_learning` are distinct downstream effects. Dual projection is not evidence of redundant storage.
- `backend/app/services/domain_events.py`: `DomainEventRelay.run_once` claims and dispatches events and calls `complete_domain_event` or `fail_domain_event`. `_dispatch` consumes `aggregate_id` and fixed event types for privacy-safe correlation. Existing offline synthetic relay harness tests handler effects, but does not prove deployed Postgres durability or external provider effects.

## Initial ownership map and decisions
| Boundary | Source-observed owner | Open question | Decision |
|---|---|---|---|
| Plan→orchestration run | ChatOrchestrationService | Other entrypoints bypassing this link; runtime frequency | KEEP + VERIFY |
| Connector write→outcome | ChatConnectorExecutionService | Authorization, uncertain writes, retries, cross-engine duplication | KEEP + AUDIT |
| Terminal run truth and projections | execution_outcome.py | All writers/readers and migration-safe consistency | KEEP canonical contract; dual projection NOT retirement-certified |
| Outbox→consumer | DomainEventRelay | Actual registered consumers, Postgres delivery and retries | KEEP + VERIFY |

## Findings and remediation backlog
- **G26-EX-001 / P1**: Plan/run correlation exists conditionally in orchestration, but source inspection does not prove global coverage. Enumerate all plan/run creation paths and instrument only verified relationships; require regression tests for missing IDs and unrelated events.
- **G26-EX-002 / P0 verification**: Connector write state has claim/replay/reconciliation and outcome pathways. Build branch-by-branch authorized/denied/revoked/uncertain/retry matrix; prove no duplicate writes or fabricated completions before simplifying engines.
- **G26-EX-003 / P1**: Canonical outcome includes dual storage projections and downstream audit/notification/learning effects. Enumerate every consumer and transactional ordering; prove exact outcome truth before schema consolidation.
- **G26-EX-004 / P1**: Relay completion/failure handling exists. Require approved Postgres-backed acceptance demonstrating durable event settlement, handler side effects, retries, tenant isolation, and no raw IDs in telemetry.

## Next tranche
Inspect callers and event-handler registrations across agents/plays/workflows; map producer→event type→handler→effect, with file/line and source/runtime evidence labels. Extend existing ECO/DEC registers, not parallel retirement authority. Test and fix only source-confirmed gaps. Exact-head full CI and issue #607 approvals remain independent blockers. **No merge, deployment, production tracing, historical reconciliation or legacy retirement authorized.**
