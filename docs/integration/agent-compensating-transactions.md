# Compensating transactions (STA-107)

When an autonomous workflow run fails mid-flight, Gravitre records compensatable tool actions and can reverse CRM/ticket writes where vendor APIs allow.

## Supported undo patterns (V1)

| Forward action | Compensation |
|----------------|--------------|
| `hubspot.contacts.create` | Delete contact |
| `hubspot.deals.create` | Delete deal |
| `hubspot.notes.create` | Delete note |
| `hubspot.contacts.update` | Restore prior properties (snapshot before update) |
| `hubspot.deals.update` | Restore prior properties |
| `hubspot.deals.update_stage` | Restore prior stage |
| `zendesk.tickets.create` | Close ticket |
| `zendesk.tickets.update` | Restore prior status/priority/tags |

## Flow

1. Successful `invoke_tool` during a workflow run records a row in `workflow_compensation_records`.
2. On run failure with `_autonomous_run` parameters, pending compensations execute in reverse order.
3. Optional webhook notification via org setting `settings.enterprise.compensationNotify.connectorId` (webhook connector).

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/runs/{id}/compensate` | Manually execute pending compensations for a run |

## Audit

- `workflow.compensation.started`
- `workflow.compensation.completed`
- `workflow.compensation.notify`

## Related

- STA-106 auto-execute — sets `_autonomous_run` on workflow parameters
- STA-109 run budgets — blocks runs before side effects when capped
