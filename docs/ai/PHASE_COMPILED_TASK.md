# compiled_task projection in task_state (audit §34 item 4)

**Status:** structural (local). Does not expand the F1 ActionSpec slice. Does not change WRITE governance, G8, or ContextCompiler prompt inclusion (item 5).  
**Date:** 2026-09-17

Read-only `task_state.compiled_task` assembled once per turn from Phase A + E5 (+ F1 preflight when present):

```
objective_text
capability_id
timeframe_resolved | null
sources[{connector, resource_id, display_name}]
action_keys[]
compiled_parameters{}
clarification_decision
preflight_status
```

Not a BusinessTask runtime. Persist via `ConversationStateService` (`compiled_task` is a DEFAULT_TASK_STATE key). `enrich_task_state_patch` always reprojects so callers cannot persist a mutated blob.

E2 visibility: `sync_trace_from_task_state` links `compiled_task`, `compiled_task_capability`, and `compiled_task_preflight`.

**NOT PROVEN live:** production conversation row with `task_state.compiled_task` after a traffic ask.
