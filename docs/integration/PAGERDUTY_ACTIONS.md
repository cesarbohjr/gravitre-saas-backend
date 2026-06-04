# PagerDuty agent tools (STA-38 / v2)

Requires a connected PagerDuty OAuth connector (STA-37). Write actions use the PagerDuty `From` header (requester email from OAuth user, connector config, or `from_email` param). Read actions do not require `From`.

## v1 actions (write)

| Action | Params |
|--------|--------|
| `pagerduty.incidents.acknowledge` | `incident_id` |
| `pagerduty.incidents.add_note` | `incident_id`, `content` (or `note` / `body`) |
| `pagerduty.incidents.escalate` | `incident_id`, optional `escalation_level` (defaults to current + 1) |

## v2 read actions

| Action | Params |
|--------|--------|
| `pagerduty.incidents.get` | `incident_id` |
| `pagerduty.incidents.list` | optional `statuses` / `status`, `service_ids`, `urgencies`, `limit` (max 100) |
| `pagerduty.incidents.notes.list` | `incident_id` |
| `pagerduty.services.list` | optional `query` / `q`, `limit` |
| `pagerduty.oncalls.list` | optional `schedule_ids`, `escalation_policy_ids`, `limit` |

List filters accept a comma-separated string or JSON array.

## v2 write actions

| Action | Params |
|--------|--------|
| `pagerduty.incidents.resolve` | `incident_id`, optional `resolution` / `resolve_note` / `note` |
| `pagerduty.incidents.reassign` | `incident_id`, `user_id` (or `userId` / `assignee_id`) |

Optional on all actions: `from_email` (write only), `connector_id`.

### Examples

```json
{
  "action": "pagerduty.incidents.list",
  "params": { "statuses": ["triggered", "acknowledged"], "limit": 10 }
}
```

```json
{
  "action": "pagerduty.incidents.resolve",
  "params": { "incident_id": "PABC123", "resolution": "Root cause fixed in deploy v42" }
}
```

### Agent scopes

| Scope | Actions |
|-------|---------|
| `pagerduty:incidents:read` | `incidents.get`, `incidents.list`, `incidents.notes.list` |
| `pagerduty:incidents:write` | All v1 write + `incidents.resolve`, `incidents.reassign` |
| `pagerduty:services:read` | `services.list` |
| `pagerduty:oncalls:read` | `oncalls.list` |
| `pagerduty:*` | All of the above |

## Triggers

See [PAGERDUTY_TRIGGERS.md](./PAGERDUTY_TRIGGERS.md).

## Code

- `backend/app/connectors/pagerduty.py`
- `backend/app/services/tool_service.py`
- `backend/app/services/agent_tool_permissions.py`
