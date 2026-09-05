# Unified-turn LIVE write-narration gap — closed by evidence, not by a new hook

Date: 2026-09-05

## The gap as stated

`voice_tool_narration.will_execute_staged_connector_write`'s own docstring
listed an explicit, accepted false negative: "unified-turn LIVE turns that
resolve a write before ever reaching this call site are still silent here."
This prompt asked that gap to be closed.

## Finding

Traced every branch of `apply_unified_turn_live()` in
`backend/app/services/unified_turn_reasoning_service.py` (the "unified-turn
LIVE" path) that can return a write-shaped `stop_pipeline: True` payload:

1. **Write-approval staging branch** (`plan.requires_approval` /
   `requires_write_approval`) — stages `pending_task.status ==
   "awaiting_confirm"` and returns a confirm-ask message. It never calls a
   connector/tool executor. Real execution only happens later, when the user
   confirms — and a bare confirm of an already-staged write is caught by
   `has_pending_family` and exits this file with `return None` *before*
   `run_unified_turn_shadow` is even called, deferring to the classical path.
2. **Orchestration "stage before defer" branch** — calls
   `ChatOrchestrationService._build_plan` and `_present_plan_confirm` only;
   never reaches `_start_execution` / `_execute_current_step` (the service's
   real execution methods) from this call site.
3. **Bare confirm of an already-staged `connector_action` or
   `connector_orchestration`** — always exits with `return None` from this
   file, before the single-model-call (`run_unified_turn_shadow`) even runs.

**Conclusion: `apply_unified_turn_live` never itself executes a real
connector write.** Every real write this file can lead to executes through
one of the two call sites that already have EXECUTING-phase voice narration:

- `run_connector_turn` in `agent_intelligence.py` — covered by
  `will_execute_staged_connector_write` / `narrate_connector_write_executing`
  (this session's earlier phase3-connector-gap fix).
- Classical ReAct `tool_start`/`tool_complete` SSE events — covered by
  `narrate_tool_started` / `narrate_tool_completed` in `cognitive_llm.py`
  (Phase 2/3 of the conversational-realism work).

So the originally-flagged "silent gap" does not correspond to an actual
reachable code path where a write executes with no narration coverage. The
honest, correct fix is **not** a new narration hook in this file — per
`will_execute_staged_connector_write`'s own hard constraint, adding a
speculative "I'm doing that now" hook to a branch that only ever stages an
approval ask or defers would be a **false positive** (claiming execution
state that isn't true yet), which this program's Phase 3 rules treat as
strictly worse than the silence it would replace.

## Evidence

`backend/tests/services/test_unified_turn_live_write_execution_narration_gap.py`
— 7 mutation-proof tests, all passing:

- `TestWriteApprovalStagingNeverClaimsExecution` (2 tests) — the
  write-approval branch stages `awaiting_confirm` without any
  execution-claiming language, and `spoken_mode` does not alter that payload
  at all (proves no narration hook was smuggled in).
- `TestBareConfirmOfStagedWriteNeverResolvesInsideLive` (2 tests) — a bare
  "yes" for a staged `connector_action` or `connector_orchestration` always
  returns `None` from this file and never calls `run_unified_turn_shadow`.
- `TestOrchestrationBeforeDeferStagesOnlyNeverExecutes` (1 test) — the
  orchestration stage-before-defer branch never calls
  `_start_execution`/`_execute_current_step`.
- `TestSpokenModeSignalReachesThisService` (2 tests) — confirms
  `spoken_mode` is genuinely threaded into `run_unified_turn_shadow` (for
  SPOKEN-register selection only), not into any execution-claiming behavior.

```
7 passed in 4.09s
```

## Scaffold/authorization note

Documentation and test-only change. No customer-facing price, claim, badge,
or entitlement toggle was touched — (b) internal engineering evidence, not
separately authorized customer-facing product wording.
