# Salesforce tool actions

All actions are invoked via `invoke_tool(ctx, action, params)` (STA-10). Requires an org Salesforce connector with OAuth (STA-30) and agent scopes (STA-11).

## v1 (STA-31)

| Action | Params |
|--------|--------|
| `salesforce.leads.get` | `lead_id`, optional `fields[]` |
| `salesforce.leads.update` | `lead_id`, `fields{}` (Salesforce field API names) |
| `salesforce.accounts.get` | `account_id`, optional `fields[]` |
| `salesforce.opportunities.create` | `fields{}` (e.g. `Name`, `StageName`, `CloseDate`, `AccountId`) |
| `salesforce.opportunities.update_stage` | `opportunity_id`, `stage_name` |
| `salesforce.tasks.create` | `subject` and/or `fields{}`; optional `who_id`, `what_id`, `description`, `status` |

### Example: inbound lead → opportunity

```json
[
  {
    "action": "salesforce.leads.update",
    "params": {
      "lead_id": "00Q...",
      "fields": { "Status": "Working - Contacted" }
    }
  },
  {
    "action": "salesforce.opportunities.create",
    "params": {
      "fields": {
        "Name": "Acme — Expansion",
        "StageName": "Prospecting",
        "CloseDate": "2026-06-30",
        "AccountId": "001..."
      }
    }
  },
  {
    "action": "salesforce.tasks.create",
    "params": {
      "subject": "Follow-up call",
      "who_id": "00Q...",
      "description": "Logged by Gravitre Operator"
    }
  }
]
```

### Agent scopes

| Scope | Actions |
|-------|---------|
| `salesforce:leads:read` | `salesforce.leads.get` |
| `salesforce:leads:write` | `salesforce.leads.update` |
| `salesforce:accounts:read` | `salesforce.accounts.get` |
| `salesforce:opportunities:write` | `salesforce.opportunities.create`, `salesforce.opportunities.update_stage` |
| `salesforce:tasks:write` | `salesforce.tasks.create` |
| `salesforce:*` | All of the above |

## v2

| Action | Params |
|--------|--------|
| `salesforce.leads.create` | `fields{}` (e.g. `LastName`, `Company`, `Email`) |
| `salesforce.leads.search` | `soql` **or** `email` / `company` / `status`, optional `limit` |
| `salesforce.opportunities.get` | `opportunity_id`, optional `fields[]` |
| `salesforce.opportunities.update` | `opportunity_id`, `fields{}` |
| `salesforce.accounts.create` | `fields{}` |
| `salesforce.accounts.update` | `account_id`, `fields{}` |

### Example: search leads by email

```json
{
  "action": "salesforce.leads.search",
  "params": { "email": "alex@acme.com", "limit": 10 }
}
```

### Agent scopes (v2)

| Scope | Actions |
|-------|---------|
| `salesforce:opportunities:read` | `salesforce.opportunities.get` |
| `salesforce:accounts:write` | `salesforce.accounts.create`, `salesforce.accounts.update` |

Inbound CRM events → workflows: see [SALESFORCE_TRIGGERS.md](./SALESFORCE_TRIGGERS.md) (STA-32).

See [SALESFORCE.md](./SALESFORCE.md) for OAuth setup.
