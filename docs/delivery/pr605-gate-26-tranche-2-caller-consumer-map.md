# PR605 Gate 26 Tranche 2 — execution caller and event-consumer coverage map

Evidence date: 2026-11-05. Branch: `feat/gravitre-unified-ecosystem-modernization`. Source-level map; not an exhaustive runtime trace. Extends the governing PR605 modernization plan, Gate 26 tranche 1/2, ECO remediation and DEC retirement registers.

## Source-backed execution ownership

| Surface | Entry / registration | Downstream owner | Safety / evidence boundary |
| --- | --- | --- | --- |
| Chat orchestration | `backend/app/services/chat_orchestration_service.py:1487` | Connector `execute_plan` | Human-confirmed sequential path; `own_terminal_outcome=False` |
| Chat orchestration | `chat_orchestration_service.py:1628` | Connector `execute_plan` | Parallel batch restricted to read-only, no approval; `own_terminal_outcome=False` |
| Chat orchestration | `chat_orchestration_service.py:1846` | Connector `execute_plan` | Policy-authorized sequential path; `own_terminal_outcome=False` |
| Orchestration terminal | `chat_orchestration_service.py:1910-1980` | Persisted run terminal or orphan `finalize_execution_outcome(persist_run=False)` | Late-run recovery attempted when steps exist; fallback also possible after failed late-run creation |
| Connector execution | `backend/app/services/chat_connector_execution_service.py` | Central connector execution and effect finalizer | Speculative unadopted outcome defers; uncertain write effect cannot be called verified success |
| Write authority | `backend/app/services/write_authority.py` | Shared write check | Human/run/policy/compensation/internal authority; policy forbidden for always-human-approval actions |
| Voice cancellation | `backend/app/services/turn_cancellation.py` | Bound per-turn cancellation | Cancelled turn's mutable request-state writes are dropped |
| Workflow strategy | `backend/app/services/workflow_execution_strategy.py` | Plan/result mapping | Source-backed, not proof of provider or run effects |
| Agent selection | `backend/app/operators/agent_intelligence.py` | Agent decision/selection | Decision owner is not automatically execution owner |
| Autonomous loop | `backend/app/services/autonomous_execution_loop.py` | Decision-loop state | Does not itself establish tool execution or connector authorization |
| Temporal worker | `backend/app/temporal/worker.py:33-81` | Six registered workflows, eight activities | Only starts with TEMPORAL_HOST; actual deployed worker and dispatch remain unverified |

## Domain-event registration and side-effect consumers

| Event | Registration | Handler | Side effect and safety |
| --- | --- | --- | --- |
| `source.disconnected` | `backend/app/services/source_lifecycle.py:216-224` | `handle_source_disconnected` | Connector-derived data/memory purge, dry-run unless SOURCE_PURGE_DRY_RUN=false; inspect tenant isolation and lineage |
| `customer.message_received` | `backend/app/services/customer_observation_feed.py:158-163` | `handle_customer_message` | Re-reads provider message and extracts observations; skips without filed entity; provider and idempotency need acceptance |
| `execution.outcome_finalized` | `backend/app/services/outcome_learning_handler.py:404-416` | `handle_execution_outcome_finalized` | Outcome learning/work-object/prediction effects; registration gated by OUTCOME_LEARNING_HANDLER_ENABLED |
| Relay startup | `backend/app/schedulers/domain_event_relay_scheduler.py:85-113` | Registers above handlers, starts relay | Disabled unless DOMAIN_EVENT_RELAY_ENABLED and positive interval; handler names persisted for partial retries |
| Outbox producers | `supabase/migrations/20261012024141_domain_event_outbox.sql` | Trigger on workflow_runs terminal status, connector disconnect | Same-transaction event creation, unique event type+idempotency key; SQL alone not proof of deployed schema |

## Durable PostgreSQL verification

An **existing** real PostgreSQL suite, `backend/tests/db/test_domain_event_outbox_pg.py`, contains tests for transaction rollback, same-transaction event emission, repeated terminal status deduplication, concurrent SKIP LOCKED claims, lease fencing, retry/dead-letter, RLS, two-relay delivery and durable handler progress after failure. It uses `backend/tests/db/pg_harness.py` to start a throwaway local PostgreSQL cluster. PR605 adds `.github/workflows/pr605-gate26-postgres-outbox.yml` to execute this suite on GitHub runners with explicit PostgreSQL binary presence check so a skip cannot be misrepresented as certification. **Execution and pass status must be read from exact-head CI**.

## Coverage limitations and required closure

1. The GitHub code search is indexed on the default branch, not guaranteed to include all PR605-only call sites. This table is grounded in directly fetched PR605 files and known registrations, not a full repository-wide dynamic call graph.
2. Agent, play, workflow and connector registries include dynamically injected callbacks and database RPCs; static AST output is only a candidate list. The owner inventory was expanded from 12 to 20 source modules; `pr605-cross-surface-ownership.yml` assertion was updated to match.
3. Feature flags and worker selection in deployed environments remain unattested; disabled handlers do not count as executed.
4. Verify CI scoped tests and isolated PostgreSQL suite pass on the **same final head**. Validate no skipped PG tests; inspect actual test counts and artifacts.
5. Runtime evidence with typed shared identifiers and privacy approval is separately required before asserting complete execution/consumer effects or approving any legacy retirement.

**Decision:** KEEP existing guarded paths. No evidence yet supports deleting or consolidating any registered handler, execution engine or run projection. Tranche 2 remains open pending CI and runtime coverage certification.
