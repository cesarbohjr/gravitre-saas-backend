# Module A — Canonical Execution Outcome Record (STA-329)

## Phase 0 answers

### 1. Async worker architecture

**Real Redis list queue + in-process asyncio BLPOP poller** (STA-94), co-located in the FastAPI process.

| Piece | Location |
|-------|----------|
| Enqueue | `backend/app/workers/workflow_dispatch.py` → `workflow_queue.enqueue_workflow_run` (`RPUSH gravitre:workflow-runs`) |
| Consumer | `backend/app/workers/workflow_worker.py` started from `main.py` lifespan |
| Execute | Same `execute_workflow_steps` / graph `_finalize_run` as sync path |

Not Celery, RQ, Postgres poller, Railway cron, or Temporal (Temporal is for other domains).

`finalize_execution_outcome()` is called from the execute stack the worker already runs — plus the worker `except` crash path so runs cannot stick on `running`.

### 2. STA-271 / STA-274 current state

| Ticket | Linear | Residual this module finishes |
|--------|--------|-------------------------------|
| STA-271 | Done | Contract `runs`/`run_steps` declared canonical; execution still wrote via `workflow_runs` + mirror, with **six disagreeing terminal writers**. Module A makes terminal writes go through one function → `update_run` (mirror contained in repository). |
| STA-274 | Done | `write_audit_event` dual-writes `audit_logs` (customer canonical) + `audit_events` (metrics). Module A uses only that writer for execute outcomes. |

## Schema decision

**Outcome event shape** (`ExecutionOutcomeEvent`):
`run_id`, terminal `status` (`completed` \| `failed` \| `cancelled` \| `partial_success`), `actor_id`, `source`, `error_summary`, `timestamp`, `verified_output` (summary / result_url — never a bare success flag).

**Runs table:** Customer-facing canonical = contract `runs` (STA-272). Terminal persist = `repository.update_run` → `workflow_runs` then `mirror_legacy_run_to_contract`. No surface may write either table for terminal outcomes outside `finalize_execution_outcome`. Invert primary insert to `runs` is a follow-on cutover; dual-write is no longer surface-level.

**Audit:** Sole writer `write_audit_event` / `emit_execute_*`. Customer read store remains `audit_logs`.

## Fanout

1. Persist run (when `run_id` + `persist_run`)
2. Audit `workflow.execute.{completed,failed,cancelled}`
3. Notification `run_{completed,failed,cancelled}` — never `task_completed` on failure
4. Learning `intelligence_outcome_events` on **every** terminal state
5. Failure-alert correlation subscriber (`correlate_observed_run_failure`) — requires `workflow_id`

## Migrated call sites

1. `chat_orchestration_runs.finalize_orchestration_run` (bridge deleted)
2. `chat_connector_execution_service.execute_plan` (failure paths included)
3. `execution_engine_runtime._finalize_run` (canvas via `source=canvas` when parameters say so)
4. `workflows/execute.py` terminal block
5. `workflow_worker.process_workflow_run_job` crash finalize
