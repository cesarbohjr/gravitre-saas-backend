# Phase 9 — Action Plans

## Goal
Return structured, multi-step operator plans with explicit explainability and permission guardrails. No actions are executed automatically.

## Endpoint

`POST /api/v1/operator/action-plan`

### Request

```json
{
  "primary_context": { "type": "run|workflow|connector|source", "id": "<uuid>" },
  "related_contexts": [{ "type": "...", "id": "<uuid>" }],
  "operator_goal": "investigate failure"
}
```

### Response (summary)

```json
{
  "plan_id": "<uuid>",
  "title": "Action Plan",
  "summary": "…",
  "steps": [
    {
      "id": "step-1",
      "title": "Review run details",
      "description": "…",
      "step_type": "review_run",
      "linked_entity": { "type": "run", "id": "<uuid>" },
      "dependencies": [],
      "explanation": {
        "data_used": ["run.summary", "run.steps"],
        "environment": "staging",
        "permissions_required": ["member", "approver"],
        "approval_required": true,
        "admin_required": true,
        "executable": false,
        "draft_only": true,
        "confirmation_required": false
      }
    }
  ],
  "guardrails": {
    "environment": "staging",
    "approval_requirements": ["Approval required for workflow execution"],
    "admin_restrictions": ["Admin required for connector edits"],
    "execution_restrictions": ["Execution requires explicit confirmation"]
  }
}
```

## Frontend Components

- `ActionPlan`
- `ActionPlanStep`
- `ActionProposalCard`
- `ContextPanel` (guardrails box)

## Explainability Requirements

Each step includes:
- `data_used`
- `environment`
- `permissions_required`
- `approval_required`
- `admin_required`
- `executable` vs `draft_only`
- `confirmation_required`

## Safety Rules

- No auto-execution.
- Approval requirements and admin restrictions are always visible.
- Requests are org-scoped and environment-scoped.

## Known limitations

- Initial planning is deterministic (rule-based).
- Step dependencies are illustrative and may not reflect real execution graphs yet.

