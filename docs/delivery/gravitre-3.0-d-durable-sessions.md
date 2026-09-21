# Gravitre 3.0-D — durable work sessions (2026-09-19)

**Status:** Source **UNIT_TEST**. Resume golden on E5 `ExecutionPlan`. **Not** a second Cowork worker runtime. Production crash-resume **UNIT**; live plan-id persist **PASS**.

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
- Production long-task resume: **PARTIAL** — isolated Apollo stage conv `2ec268a2-…` kept plan `752df0d0-…` through yes-wait (`sent_claim=false`). `durable_checkpoint` was not on the stored task_state, so crash-resume golden stays **UNIT_TEST**.

Lane B production and a separate worker process remain forbidden.
