# QuickBooks tool actions

Invoked via `invoke_tool(ctx, action, params)` (STA-10). Requires QuickBooks OAuth (STA-33) and agent scopes (STA-11).

## v1 read (STA-34)

| Action | Params |
|--------|--------|
| `quickbooks.invoices.list` | optional `limit` / `max_results`, `start_position` / `startPosition` |
| `quickbooks.invoices.get` | `invoice_id` |
| `quickbooks.payments.list` | optional `limit`, `start_position` |
| `quickbooks.vendors.get` | `vendor_id` |

### Example: overdue invoice summary prep

```json
{
  "action": "quickbooks.invoices.list",
  "params": { "limit": 50 }
}
```

### Agent scopes

| Scope | Actions |
|-------|---------|
| `quickbooks:invoices:read` | `quickbooks.invoices.list`, `quickbooks.invoices.get` |
| `quickbooks:payments:read` | `quickbooks.payments.list` |
| `quickbooks:vendors:read` | `quickbooks.vendors.get` |
| `quickbooks:*` | All of the above |

## v2 read (STA-34)

| Action | Params |
|--------|--------|
| `quickbooks.customers.list` | optional `limit`, `start_position` |
| `quickbooks.customers.get` | `customer_id` |
| `quickbooks.customers.search` | `display_name` and/or `email`, optional `limit` |
| `quickbooks.vendors.list` | optional `limit`, `start_position` |
| `quickbooks.accounts.list` | chart of accounts; optional `limit`, `start_position` |
| `quickbooks.bills.list` | AP bills; optional `limit`, `start_position` |
| `quickbooks.bills.get` | `bill_id` |
| `quickbooks.companyinfo.get` | (none) — company metadata for connected realm |

### Example: find customer then list open bills

```json
[
  {
    "action": "quickbooks.customers.search",
    "params": { "display_name": "Acme" }
  },
  {
    "action": "quickbooks.bills.list",
    "params": { "limit": 25 }
  }
]
```

### Agent scopes (v2)

| Scope | Actions |
|-------|---------|
| `quickbooks:customers:read` | `quickbooks.customers.list`, `.get`, `.search` |
| `quickbooks:accounts:read` | `quickbooks.accounts.list` |
| `quickbooks:bills:read` | `quickbooks.bills.list`, `quickbooks.bills.get` |
| `quickbooks:company:read` | `quickbooks.companyinfo.get` |

`quickbooks.vendors.list` uses `quickbooks:vendors:read` (same as v1 `vendors.get`).

See [QUICKBOOKS.md](./QUICKBOOKS.md) for OAuth setup.
