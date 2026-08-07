# Phase 1 — AI-logic sequencing surface wiring audit

## Department chat agents

- No separate sales/support/ops reasoners. UI department is a scope overlay on
  `/api/assistant/chat` → `execute_task_streaming`.
- **Gap fixed:** department now flows into `execute_task_streaming` →
  classification + persona (not only `prepare_stream` system prompt).

## Custom chat agents

- Capability exists (`/agents/[id]/chat`).
- **Critical gap fixed:** unified LIVE used `permitted=["*"]` and ignored
  `agent_id`. Now resolves agent row via `resolve_agent_record` and
  `resolve_permitted_tools` before `apply_unified_turn_live`.
- **FE gap fixed:** removed hardcoded 5-tool list from agent chat transport.

## Meson

- **Gap fixed:** deploy maps GoalService types → canvas types, persists
  `from_node_id`/`to_node_id`, and runs `sync_builder_graph` (same
  `assert_bindings_valid` as PUT `/builder`) before audit `meson.workflow.created`.
- HTTP 400 with `{message, errors}` on validation failure.
- Hydration prefers declared edges over sequential fallback.

## Canvas lifecycle

- Save already ran binding validation; **durability gap fixed:** preflight
  compile+validate before `delete_workflow_graph`.
- Delete node: canvas state already cleaned connections; API
  `delete_workflow_node` now cascades incident edges.
- Duplicate step: ConfigPanel Duplicate/Delete wired; duplicate gets new UUID
  and empty `connections`.
- Rewire remains add-only (document; optional UX later).

## Standing dual-path note (not closed here)

- `execute_task` (jobs/swarm/handoff) still bypasses unified-turn — same
  “one mechanism” debt already tracked for chat vs classical. Out of Phase 1
  canvas/Meson scope; flagged for follow-on.

## Tests

- `backend/tests/workflows/test_phase1_wiring_audit.py`
- Existing builder edge + binding suites still apply.
