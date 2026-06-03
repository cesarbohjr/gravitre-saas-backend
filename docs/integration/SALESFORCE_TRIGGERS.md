# Salesforce inbound triggers (STA-32)

Salesforce CRM events start workflow runs through the merged step executor (STA-12). Unlike HubSpot app-level webhooks, each org connector has its own inbound URL and HMAC secret.

## Per-connector inbound URL

After OAuth connect, the API stores `connectors.config.webhook_secret`. Admins configure Salesforce (Flow, Apex, or middleware) to POST JSON to:

```text
{API_PUBLIC_URL}/api/webhooks/salesforce/inbound/{connector_id}
```

Sign the raw body with HMAC-SHA256 (hex) using the webhook secret and send header:

```text
X-Gravitre-Signature: <hex digest>
```

Optional prefix `sha256=` is accepted.

List bindings and copy URL + secret:

```http
GET /api/connectors/{connector_id}/salesforce-triggers
```

## Per-org trigger bindings

```http
PUT /api/connectors/{connector_id}/salesforce-triggers
```

```json
{
  "triggers": [
    {
      "event": "lead.created",
      "workflow_id": "<workflow-def-uuid>",
      "active": true,
      "label": "New lead"
    },
    {
      "event": "opportunity.stageChange",
      "stage": "Closed Won",
      "workflow_id": "<workflow-def-uuid>",
      "active": true
    }
  ]
}
```

Supported events: `lead.created`, `opportunity.stageChange`.

## Inbound payload (from Salesforce Flow / callout)

Single event or JSON array batch:

```json
{
  "event": "lead.created",
  "recordId": "00Qxxxxxxxx",
  "organizationId": "00Dxxxxxxxx",
  "changedFields": { "Status": "Open" },
  "occurredAt": "2026-05-29T12:00:00Z"
}
```

Stage change example:

```json
{
  "event": "opportunity.stageChange",
  "recordId": "006xxxxxxxx",
  "stageName": "Qualification",
  "changedFields": { "StageName": "Qualification" }
}
```

Aliases accepted: `Lead.created`, `Opportunity.stageChange`, etc.

## Run context

Workflow `parameters` include:

- `salesforce_event` — normalized metadata
- `lead` or `opportunity` — `{ id, fields }` (enriched via REST API when OAuth token is available)
- `trigger` — the binding that matched

`workflow_runs.trigger_type` is `salesforce`.

## Code

- `backend/app/connectors/salesforce_webhooks.py` — signature, normalization
- `backend/app/services/salesforce_trigger_service.py` — dispatch
- `backend/app/routers/webhooks/salesforce_inbound.py` — inbound POST
- `backend/app/routers/salesforce_triggers.py` — admin bindings API
