# Workflows Orchestrator UI (Phase 11)

## Purpose
Define a minimal orchestration view for workflows that mirrors agentic
orchestrator patterns while staying aligned with the existing Gravitre data model.

## Scope
- Workflows list: link to orchestration view in workflow detail.
- Workflow detail: read-only orchestration preview based on definition metadata.
- Runs: execution flow summary (per-step status).
- Approvals: human gate checkpoints.

## Orchestration View (Workflow Detail)
Display a linear, read-only list of workflow steps as orchestration nodes.
Each node shows:
- Step name + type
- Role tag (from metadata or type mapping)
- Agent link (agent_id)
- Next agent link (next_agent_id)
- Task summary (task)
- Approval gate badge (approval_gate)

### Step Metadata Contract (in definition JSON)
Each step may include:
- `metadata.role`: string
- `metadata.agent_id`: operator id (uuid string)
- `metadata.next_agent_id`: operator id (uuid string)
- `metadata.task`: string
- `metadata.approval_gate`: boolean

Example:
```json
{
  "id": "step-2",
  "name": "Marketing handoff",
  "type": "noop",
  "metadata": {
    "role": "Marketing",
    "agent_id": "8c4fd9d0-1b12-4cf2-86f2-2c7a9e0b2e5d",
    "next_agent_id": "77a1d3c9-0f2f-4f6a-9c8b-5bd33f96c2a0",
    "task": "Qualify lead and handoff to sales.",
    "approval_gate": true
  }
}
```

## Runs (Execution Flow)
Show a compact execution flow summary above the step table:
- Step order
- Step status badge
- Step type label

## Approvals (Human Gates)
Show “Approval gate” in approvals list to reinforce gate checkpoints.

## Cross-Links
- From orchestration node to Agent profile: `/agents/{agent_id}`
- From orchestration view to Runs: `/runs`
- From approval list to Run detail: `/runs/{run_id}`

## Design Notes
- No drag-and-drop canvas
- Use existing card/table styles and muted badges
- Keep layout consistent with Gravitre shell
