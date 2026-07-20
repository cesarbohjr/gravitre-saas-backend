# Module A — Non-terminal writer audit (explicit)

**Date:** 2026-07-20  
**Question:** Do remaining `emit_notification` call sites outside `finalize_execution_outcome` ever transition a **workflow run** to a terminal state without Module A fanout?

## Decision

They are **not** Module A terminal writers. Each either (a) notifies a non-run lifecycle event, or (b) notifies a mid-flight / start state while the actual terminal path already goes through `finalize_execution_outcome` / `execute_workflow_steps` → `_finalize_run`.

| Call site | Event type | Terminal workflow_run? | Path to terminal |
|-----------|------------|------------------------|------------------|
| `routers/lite.py` | `run_started` | No — start only | `execute_workflow_steps` / worker → finalize |
| `routers/workflows.py` (~1798) | `approval_needed` | No — pending approval | Approve/reject → finalize (`cancelled` / execute) |
| `chat_connector_execution_service.py` | `approval_needed` | No — HITL gate | Confirm execute → chat connector / orch finalize |
| `marketplace/service.py` | `system` (install) | N/A — marketplace install | Never creates a terminal `workflow_runs` outcome |
| `swarm_coordinator_service.py` | `run_completed` | N/A — `agent_swarm_run` entity | Swarm session lifecycle, not `workflow_runs` Module A |
| `intelligence_pack_tools.py` | `task_completed` | N/A — pack tool UX toast | Pack tool success; no `workflow_runs` terminal writer |

## Guarantee

No listed site updates `workflow_runs.status` to `completed` / `failed` / `cancelled` / `partial_success`. Terminal status writes for live executions remain behind:

1. `finalize_execution_outcome()` (canonical), or  
2. Intentional dry-run / digital-twin bypass (documented separately), or  
3. The loud `MODULE_A_FINALIZE_FAILED_FALLBACK_STATUS_STAMP` safety net in `chat_orchestration_runs.py`.

If a future change makes pack tools or swarm sessions persist `workflow_runs` terminals, those paths must call `finalize_execution_outcome` — do not extend the bare `emit_notification` sites.
