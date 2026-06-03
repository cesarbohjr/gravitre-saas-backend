# HubSpot inbound triggers (STA-16)

HubSpot CRM events start workflow runs through the merged step executor (STA-12).

## Platform setup (operators)

Full runbook: **[HUBSPOT_PLATFORM_SETUP.md](./HUBSPOT_PLATFORM_SETUP.md)** ([STA-125](https://linear.app/staqbot/issue/STA-125)).

Summary:

1. Create a **Legacy public app** in the HubSpot developer portal (not MCP Auth Apps).
2. **Redirect URL:** `{API_PUBLIC_URL}/api/connectors/oauth/hubspot/callback`
3. **Webhook target (STA-16):** `{API_PUBLIC_URL}/api/webhooks/hubspot/inbound`
4. Env vars:
   - **OAuth + tools:** `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET`, `CONNECTOR_SECRETS_ENCRYPTION_KEY`, `API_PUBLIC_URL`
   - **Inbound triggers only:** also `HUBSPOT_APP_ID`, `HUBSPOT_DEVELOPER_API_KEY` (Developer API key + `hapikey`, not customer Private App token)
   - `HUBSPOT_CLIENT_SECRET` also verifies `X-HubSpot-Signature-v3` on inbound webhooks

On each customer **Connect HubSpot** (OAuth complete), the API syncs app-level subscriptions for:

| Event | Notes |
|-------|--------|
| `contact.creation` | New contacts (e.g. form submissions) |
| `deal.propertyChange` | `dealstage` property only |

## Per-org trigger bindings

Admins map HubSpot events to active `workflow_defs` on a connector:

```http
PUT /api/connectors/{connector_id}/hubspot-triggers
```

```json
{
  "triggers": [
    {
      "event": "contact.creation",
      "workflow_id": "<workflow-def-uuid>",
      "active": true,
      "label": "New lead"
    },
    {
      "event": "deal.propertyChange",
      "property": "dealstage",
      "workflow_id": "<workflow-def-uuid>",
      "active": true
    }
  ]
}
```

Routing uses `connectors.config.hub_id` (set at OAuth) to match `portalId` in webhook payloads.

## Run context

Workflow `parameters` include normalized records:

- `hubspot_event` — raw event metadata
- `contact` or `deal` — `{ id, properties }` (enriched via CRM API when OAuth token is available)
- `trigger` — the binding that matched

`workflow_runs.trigger_type` is `hubspot`.

## Demo org seed

`org_seed_service` creates a matching `workflow_defs` row and stores `organizations.settings.onboarding.demo_hubspot_workflow_id`. The first HubSpot OAuth connect auto-installs a `contact.creation` → demo workflow binding.

## Code

- `backend/app/connectors/hubspot_webhooks.py` — signature, subscriptions
- `backend/app/services/hubspot_trigger_service.py` — dispatch
- `backend/app/routers/webhooks/hubspot_inbound.py` — inbound POST
- `backend/app/routers/hubspot_triggers.py` — admin bindings API
