# Gravitre 3.0-D — durable work sessions (2026-09-19)

**Status:** Source **UNIT_TEST**. Resume golden on E5 `ExecutionPlan`. **Not** a second Cowork worker runtime. LIVE_USER_PROVEN long-task **NOT RUN**.

## What shipped

| Piece | Behavior |
|-------|----------|
| Session machine | Projection of plan terminal + `pending_task` (`WAITING_APPROVAL` ↔ `awaiting_confirm`) |
| Checkpoint | Before WRITE approval: intent, approval id, inputs, expected result |
| Secrets | Token/HMAC/password keys stripped from checkpoint JSON |
| Resume | Same `plan_id`; `continuation_of_plan_id` set |
| Deliverable | Diagnosis / evidence / causes / uncertainties / actions required when flagged |
| Verify | COMPLETE blocked on missing evidence, unverified WRITE, blockers |
| Runtime | `e5_execution_plan` only |

## Gate

- Resume same `plan_id`: UNIT_TEST (`backend/tests/services/test_durable_work_session.py`)
- Production long-task resume: **NOT RUN**

Lane B production and a separate worker process remain forbidden.
