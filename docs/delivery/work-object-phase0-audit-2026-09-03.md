# WorkObject Phase 0 Audit (2026-09-03)

## Pre-flight status

- Branch baseline: `main` at local start; pulled from `origin/main`.
- CI baseline on `main`: **not green** at audit start (latest `CI` workflow failures present).
- Standing live battery rerun executed locally:
  - `scripts/verify-pending-reply-classifier-live.py` — PASS
  - `scripts/verify-conversational-path-live.py` — PARTIAL/FAIL exit (case regressions)
  - `scripts/verify-unified-turn-phase2-live.py` — FAIL exit (skipped/coverage failures)
  - `scripts/verify-unified-turn-persona-drift-live.py` — PASS
  - `scripts/verify-unified-turn-prompt-injection-live.py` — initially failed due unpack bug; fixed in this pass

## Current lifecycle tracking that exists today

- **Run-level canonical outcome tracking** via `execution_outcome.finalize_execution_outcome`.
- **BusinessOutcome projection** (read-model DTO) derived from `workflow_runs` + steps.
- **Conversation task-state continuity** in `conversations.task_state`.
- **Audit streams** via `audit_logs` + `audit_events`.
- **Memory and retrieval layers** across `agent_memories`, `org_entity_relationships`, `org_knowledge_nodes`, and intelligence events.

## Confirmed gap

No single, durable, queryable entity currently represents one business object lifecycle
across multiple consequential actions (for example one Opportunity over several runs and
days). Existing continuity is fragmented across run rows, conversation state, and memory
signals.

## Design decision for this pass

Introduce a first-class WorkObject spine that extends (not replaces) BusinessOutcome:

1. `work_objects` table for durable business entity identity and state.
2. `work_object_events` append-only timeline tying each consequential action back to the WorkObject.
3. Attribution hook at Module A (`finalize_execution_outcome`) so consequential terminal actions are captured in one canonical path.
4. Query API (`/api/work-objects`) and Activity UI tab to surface lifecycle continuity.
5. Connector SOURCE/ACTION/DESTINATION classification as a complementary axis to existing `integrationClass`.
