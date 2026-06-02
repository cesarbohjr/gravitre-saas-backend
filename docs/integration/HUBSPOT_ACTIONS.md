# HubSpot tool actions

All actions are invoked via `invoke_tool(ctx, action, params)` (STA-10). Requires an org HubSpot connector with OAuth (STA-13/14) and agent scopes (STA-11).

Inbound CRM events → workflows: see [HUBSPOT_TRIGGERS.md](./HUBSPOT_TRIGGERS.md) (STA-16).

## v1 (STA-15)

| Action | Params |
|--------|--------|
| `hubspot.contacts.get` | `contact_id` or `email`, optional `properties[]` |
| `hubspot.contacts.update` | `contact_id`, `properties{}` |
| `hubspot.notes.create` | `body`, `contact_id` and/or `deal_id` |
| `hubspot.deals.update_stage` | `deal_id`, `dealstage` |
| `hubspot.sequences.enroll` | `contact_id`, `sequence_id`, optional `sender_email` |

## v2

| Action | Params |
|--------|--------|
| `hubspot.contacts.create` | `properties{}` (e.g. email, firstname) |
| `hubspot.contacts.search` | `filter_groups[]` (HubSpot CRM search), optional `limit`, `properties[]` |
| `hubspot.deals.get` | `deal_id`, optional `properties[]` |
| `hubspot.deals.create` | `properties{}`, optional `contact_id` (association) |
| `hubspot.deals.update` | `deal_id`, `properties{}` |
| `hubspot.lists.add_contact` | `list_id`, `contact_id` |

### Example: search by company

```json
{
  "filter_groups": [
    {
      "filters": [
        {
          "propertyName": "company",
          "operator": "EQ",
          "value": "Acme Corp"
        }
      ]
    }
  ],
  "limit": 25
}
```

Reconnect HubSpot after scope changes (`crm.lists.read`, `crm.lists.write`).
