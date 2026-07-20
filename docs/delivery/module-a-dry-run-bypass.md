# Module A — Dry-run / digital-twin bypass (intentional)

## Decision

Dry-run (`workflows/dry_run.py`) and digital-twin simulation (`workflows/digital_twin.py`)
**must not** call `finalize_execution_outcome()`.

They terminate with:

- `repository.update_run(...)` for the simulation run row status
- `emit_dry_run_*` audit helpers only

## Why

Module A’s fanout (Runs notifications, learning outcomes, failure-alert correlation)
is for **customer-facing live executions**. Dry-run and twin runs are sandboxed
simulations; routing them through the same fanout would:

1. Create false “run completed / failed” notifications for operators
2. Pollute `intelligence_outcome_events` with non-production outcomes
3. Trigger failure-alert correlation on simulated failures

## Contract

| Surface | Terminal writer |
|---------|-----------------|
| Live execute / chat orch / assignment / API reject-cancel | `finalize_execution_outcome` |
| Dry-run / digital twin | `emit_dry_run_*` + `update_run` only |

If a future product wants customer-visible simulation receipts, add an explicit
opt-in path — do not silently fold dry-run into Module A fanout.
