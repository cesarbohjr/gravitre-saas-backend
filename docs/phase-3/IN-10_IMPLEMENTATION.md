# IN-10 — Slack Connector Implementation

**Status:** Implemented  
**Authority:** docs/MASTER_PHASED_MODULE_PLAN.md Part V  
**Dependencies:** IN-00, BE-20

---

## Step Type: slack_post_message

- **Dry-run:** Simulated only. Returns predicted channel + message preview. No send.
- **Execute:** Sends to Slack API only after BE-20 approvals met. Uses connector token from connector_secrets.

---

## Step Config

| Key | Required | Description |
|-----|----------|-------------|
| channel | or parameters.channel | Slack channel ID or name |
| message_input_key | no | Key in parameters for message text (default: "message") |
| connector_id | no | Connector UUID; if omitted, uses first active slack connector for org |

---

## Parameters

| Key | Description |
|-----|-------------|
| message | Message text (or key from config.message_input_key) |
| channel | Override channel (if not in config) |

---

## Connector Setup

1. Create connector: `POST /api/connectors` with `{"type": "slack", "config": {"channel": "#general"}}`
2. Set token: `POST /api/connectors/:id/secrets` with `{"key_name": "token", "value": "xoxb-..."}`

---

## Audit Events

| Action | When |
|--------|------|
| slack.send.requested | Before API call |
| slack.send.sent | Success |
| slack.send.failed | Failure (no message text; error only) |

---

## Acceptance Criteria

- [x] Dry-run shows predicted Slack action (no send)
- [x] Execute sends only when approvals satisfied
- [x] 503/failed states recorded with audit
- [x] No message text in audit logs (message_hash only)
