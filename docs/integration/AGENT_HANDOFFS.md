# Cross-agent handoffs (STA-17 / STA-18)

Agents pass structured context to the next agent via the handoff bus. Workflow steps use `metadata.next_agent_id` for automatic routing.

## Briefing schema

Stored on `agent_handoffs.briefing`:

```json
{
  "contact": { "id": "...", "properties": {} },
  "deal": { "id": "...", "properties": {} },
  "decision": { "qualified": true, "summary": "..." },
  "artifacts": [
    { "type": "hubspot_event", "data": {} },
    { "type": "source_agent_output", "data": {} }
  ]
}
```

## Workflow step contract

```json
{
  "id": "sales_to_marketing",
  "name": "Sales qualifies → Marketing enrolls",
  "type": "agent",
  "metadata": {
    "agent_id": "<sales-agent-uuid>",
    "next_agent_id": "<marketing-agent-uuid>",
    "task": "Qualify inbound lead",
    "receiver_task": "Enroll qualified lead in nurture sequence"
  }
}
```

Runtime flow:

1. Source agent runs `task` with workflow `parameters` (e.g. HubSpot `contact`).
2. Handoff row is created with briefing + audit `agent.handoff.created`.
3. Receiver agent runs `receiver_task` with briefing in the prompt.
4. Audit `agent.handoff.completed` (or `.failed`).

## Demo seed

`org_seed_service` seeds one `agent` step with Sales → Marketing `next_agent_id` on `workflow_defs`.

## Code

- `backend/app/services/handoff_service.py`
- `backend/app/workflows/handlers.py` — `AgentStepHandler`
- `supabase/migrations/20260602120000_agent_handoffs.sql`
