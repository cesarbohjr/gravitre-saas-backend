# Part 5 — action-selection unification (first slice)

**Date:** 2026-08-03  
**Prior audit:** FRAGMENTED (`action-selection-confirmation-audit.md`)  
**This slice:** shared call-time **resolve + schema gate** — not full ONE_MECHANISM

## What shipped

New module: `backend/app/services/action_selection_gate.py`

| Path | Wiring |
|------|--------|
| Workflow `invoke_tool` | `handlers.InvokeToolHandler` → `gate_workflow_invoke` before `invoke_tool` |
| Chat write staging | `validate_connector_plan` uses `schema_for_action` + alias resolve |

Shared behaviors:
- Catalog alias resolve (`outlook.*` → `microsoft365.*`, Google prefix aliases)
- `ActionWorkflowSchema` validation when a schema exists (fail closed on missing required params for workflow)

## What remains FRAGMENTED

- Three **choosers** still: LLM `tool_choice`, `ChatActionMapper`, author-time `config.action`
- ReAct reads still bypass chat schema staging
- Full ONE_MECHANISM claim deferred until classical mapper selection also goes through one catalog selector

## Verdict after this slice

**PARTIAL_UNIFIED** — one shared resolve+schema gate on chat writes + workflow invoke; selection choosers still multiple.
