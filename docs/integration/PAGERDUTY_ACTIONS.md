# PagerDuty agent tools (STA-38)

Requires a connected PagerDuty OAuth connector (STA-37). Actions use the PagerDuty `From` header (requester email from OAuth user or `from_email` param).

## v1 actions

| Action | Params |
|--------|--------|
| `pagerduty.incidents.acknowledge` | `incident_id` |
| `pagerduty.incidents.add_note` | `incident_id`, `content` (or `note` / `body`) |
| `pagerduty.incidents.escalate` | `incident_id`, optional `escalation_level` (defaults to current + 1) |

Optional on all actions: `from_email`, `connector_id`.

### Example

```json
{
  "action": "pagerduty.incidents.acknowledge",
  "params": { "incident_id": "PABC123" }
}
```

### Agent scopes

| Scope | Actions |
|-------|---------|
| `pagerduty:incidents:write` | All v1 incident actions |
| `pagerduty:*` | All of the above |

## Triggers

See [PAGERDUTY_TRIGGERS.md](./PAGERDUTY_TRIGGERS.md).

## Code

- `backend/app/connectors/pagerduty.py`
- `backend/app/services/tool_service.py`
