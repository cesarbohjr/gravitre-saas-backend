# Execution Concurrency Hardening

## Risk identified
- Duplicate execute runs can start concurrently, leading to duplicate external sends.
- Approval threshold can be met by multiple approvers at the same time, causing multiple execute transitions.

## Current state
- Pre-insert concurrency check (`check_concurrency`) is advisory only.
- Approve path updates run status without a compare-and-set guard.
- No database constraint prevents multiple active execute runs per workflow.

## Recommended fix
- Add a DB-level unique partial index to enforce a single active execute run per workflow.
- Add an atomic compare-and-set transition from `pending_approval` → `running` before execution.

## Implementation details
- Added unique partial index on `workflow_runs(org_id, workflow_id)` where run_type is `execute` and status is `pending_approval` or `running`.
- Added `try_mark_run_running(...)` to perform conditional update; only the claimant proceeds to execution.
- On insert conflicts, re-check active run and return 409 to preserve API contract while preventing duplicate execution.

## Future scaling notes
- Move approval + transition into a single SQL function with row-level locking (`SELECT ... FOR UPDATE`).
- Consider a dedicated execution worker to serialize run transitions per workflow.
