# PagerDuty inbound triggers (STA-37)

PagerDuty incident events start workflow runs through the merged step executor (STA-12).

## Per-connector inbound URL

After OAuth connect:

```text
{API_PUBLIC_URL}/api/webhooks/pagerduty/inbound/{connector_id}
```

PagerDuty sends `X-PagerDuty-Signature` (v1 HMAC-SHA256). The signing secret is stored on the connector (`webhook_secret` / `pagerduty_signing_secret`).

Configure bindings:

```http
GET /api/connectors/{connector_id}/pagerduty-triggers
PUT /api/connectors/{connector_id}/pagerduty-triggers
```

```json
{
  "triggers": [
    {
      "event": "incident.triggered",
      "workflow_id": "<workflow-def-uuid>",
      "active": true,
      "label": "New incident"
    },
    {
      "event": "incident.acknowledged",
      "workflow_id": "<workflow-def-uuid>",
      "active": true
    }
  ]
}
```

Supported events: `incident.triggered`, `incident.acknowledged`.

## Workflow parameters

Inbound payloads are normalized to:

- `pagerduty_event` — event metadata
- `incident` — `id`, `number`, `summary`, `urgency`, `status`, `html_url`
- `trigger` — binding that fired

Use these in workflow steps (e.g. create Jira issue from `incident.summary`, Slack notify).

## Code

- `backend/app/connectors/pagerduty_webhooks.py`
- `backend/app/routers/webhooks/pagerduty_inbound.py`
- `backend/app/routers/pagerduty_triggers.py`
