# Action-selection confirmation audit (Slice A · Part 5)

**Date:** 2026-08-02  
**Verdict:** **FRAGMENTED**  
**Fix in this slice:** No — report only.

## Answer

Action **selection** is not one schema-constrained mechanism across chat, agents, and workflows. Write **authority** (`catalog_write_authority`) and the **invoke spine** (`invoke_tool`) are partially reunified; which action is chosen still differs by surface.

| Path | How action is chosen | Catalog at call time | Input schema before invoke |
|------|----------------------|----------------------|----------------------------|
| Governed chat / unified turn | LLM `tool_choice: auto` **and** classical `ChatActionMapper` | Partial (two selectors) | Writes: `ActionWorkflowSchema` staging |
| ReAct agent loop | LLM `tool_choice: auto` over ToolRegistry | Yes (narrowed + permitted) | No central schema; writes → chat staging |
| Workflow `invoke_tool` | Author-time `config.action` | Executor registry only | Binding validator + executor checks |

Machine-readable detail: [`action-selection-confirmation-audit.json`](./action-selection-confirmation-audit.json).

Related: STA-305, STA-334, Part D routing audit.
