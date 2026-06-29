# Execution engine design (STA-284)

**Status:** Design baseline — incremental hardening in place  
**Date:** 2026-06-21  
**Runtime:** `backend/app/workflows/execute.py` → `execution_engine_runtime.py`  
**Related:** STA-107 compensation, STA-285 simulation, STA-287 partial failure

## Scope

Universal execution guarantees for workflow graph runs, tool invokes, and autonomous agent chains — not individual connector SDK details.

## 1. Idempotency

| Layer | Mechanism | Location |
|-------|-----------|----------|
| Tool invoke | `build_invoke_idempotency_key(ctx, action, connector_id)` dedupes retries | `tool_service.py` |
| Run identity | `compute_run_hash(definition, parameters)` | `workflows/schema.py` |
| Graph resume | Checkpoint rows on pause/approval | `execution_engine_runtime._save_checkpoint` |
| Compensation | One row per forward action in `workflow_compensation_records` | `compensation_service.py` |

**Gap:** Idempotency keys are not yet persisted across HTTP retries at the workflow-run level — callers should pass stable `run_id` / client request IDs.

## 2. Input validation

| Stage | Validation | On failure |
|-------|------------|--------------|
| Definition ingest | `validate_definition`, `validate_parameters`, size limits | `WorkflowValidationError` before run |
| Graph compile | `validate_execution_graph`, topological batches | Fail before side effects |
| Step config | Per-handler `validate_config` where implemented | Step failed, run fail-fast |
| Tool args | JSON schema on registered actions (partial) | `ERROR_CODE_VALIDATION` |

**Gap:** Not all `invoke_tool` actions enforce JSON schema at invoke time — prioritize financial/destructive actions.

## 3. Permission validation

| Check | Where |
|-------|-------|
| Org membership | `auth/dependencies.get_org_context` |
| Tool allowlist | `agent_tool_permissions.py`, workflow policy |
| Approval gates | `requires_approval` catalog flag → `RUN_STATUS_AWAITING_APPROVAL` |
| Connector entitlement | Connector health + plan limits before invoke |

**Gap:** Swarm `scopedTools` enforcement — tracked STA-263.

## 4. Rate limits

| Scope | Implementation |
|-------|----------------|
| Per-org connector | `connectors/rate_limit.py` + Supabase RPC |
| Graph parallel batch | `ThreadPoolExecutor` max 8; rate_limited flag propagates |
| Run budgets | STA-109 blocks before side effects when capped |

On rate limit: step marks `rate_limited=True`; run completes with flag for UI retry messaging.

## 5. Audit per action

Every successful/failed tool invoke and workflow transition should emit:

- `write_audit_event()` → dual-write `audit_events` + `audit_logs` (contract)
- Step lifecycle: `emit_step_*` helpers in repository
- Compensation: `workflow.compensation.*` events

**Gap:** Contract write failure is silent today — STA-274.

## Execution flow (graph)

```
validate_definition → create_run → topological batches
  → per node: permission → rate limit → handler/invoke_tool
  → on fail: fail-fast (parallel) OR compensate (autonomous CRM chain)
  → finalize_run status
```

## Demo / simulation path

Live execution and digital twin share validation; twin never calls live writes — see STA-285 and `digital_twin.py`.

## Next implementation priorities

1. JSON schema enforcement for destructive catalog actions  
2. Persist workflow-level idempotency key on `workflow_runs`  
3. Alert when `audit_logs` contract write fails  
4. Document run status `partial_success` for bulk installs (STA-287)
