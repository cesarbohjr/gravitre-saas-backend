# Intelligence lifecycle E2E acceptance gate

The workflow `Intelligence lifecycle E2E acceptance` is **manual and fail-closed**.
It runs `scripts/run-intelligence-isolated-live.py` against production, in the
isolated smoke org only (`f07e57c0-1501-4000-8000-c04e57a00001`), with a
10-minute smoke-org session minted in the job (`scripts/mint_smoke_org_session.py`).
No long-lived token or hand-written evidence is stored in GitHub.

## What one run does

1. Creates a conversation and asks chat to stage an internal Gravitre assignment
   with a unique trace id (`GV-INT-E2E-…`). Nothing external is named as a target.
2. Reads the staged action back from `GET /api/assistant/conversation/{id}/state`:
   `pending_task.type == create_assignment`, `status == awaiting_confirm`, the
   brief carries the trace, and no new assignment exists. Approval is never sent
   on model text alone.
3. Negative controls: approving from another org (403) and on another
   conversation (404) is refused, creates nothing, and leaves the action waiting.
4. Approves once (`POST …/execute`): exactly one new assignment. A second approval
   replays (`structured.replayed`) and creates nothing.
5. Reads the assignment back (`GET /api/agent-jobs/{id}`) until it finishes; it
   must complete.
6. Reads the outcome chain back (`GET /api/admin/intelligence/outcomes/trace?jobId=`):
   one outcome run, completed, whose `execution.outcome_finalized` event was taken
   by `outcome_learning.record_run_outcome`. Then checks the delivery endpoint has
   no blockers.

The uploaded report lists every check with pass/fail, the trace, job and run ids.

## Not covered (separate gates)

- **Business-metric impact**: a synthetic internal assignment has no business
  metric. Measured outcomes need a real Play or goal in an owner tenant; they are
  not inferred from a completed run.
- **Customer sentiment capture**: observations and account signals are off in
  production; this run does not turn them on.
- **Changed draft needs reapproval**: covered by unit tests of the pending-write
  revision path, not exercised live here.

## Requirements

- `DOMAIN_EVENT_RELAY_ENABLED` and `OUTCOME_LEARNING_HANDLER_ENABLED` on in
  Railway (both on since 2026-10-19).
- The backend that serves `/api/admin/intelligence/outcomes/trace` deployed.
- Each run leaves one synthetic conversation, assignment and outcome run in the
  smoke org, labelled with the trace.
