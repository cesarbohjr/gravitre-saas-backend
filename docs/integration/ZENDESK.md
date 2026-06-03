# Zendesk v1 (STA-21)

## Connector setup

1. Create connector `type=zendesk` with config `{ "subdomain": "your-subdomain" }`.
2. Store secrets via `POST /api/connectors/{id}/secrets`:
   - `email` — Zendesk agent email
   - `api_token` — API token from Admin → Apps and integrations → APIs

## Tool actions

| Action | Description |
|--------|-------------|
| `zendesk.tickets.get` | Read ticket by id |
| `zendesk.tickets.create` | Create ticket (subject, comment) |
| `zendesk.tickets.update` | Update status/priority/comment/tags |
| `zendesk.tickets.add_tags` | Add tags to ticket |

Grant scopes via agent tool permissions: `zendesk:tickets:read`, `zendesk:tickets:write`, or `zendesk:*`.
