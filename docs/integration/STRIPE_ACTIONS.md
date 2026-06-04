# Stripe agent tools (STA-35)

Read-only Stripe tools for the Finance Agent. **Separate from Gravitre platform billing** (`app.billing.stripe` uses `STRIPE_SECRET_KEY` for subscriptions/metering only).

## Connector setup

1. **Connectors → Add Stripe** with a restricted Stripe secret key (`rk_*` or `sk_*` with read-only scopes).
2. Store via **API key** field (encrypted on connector) or `connector_secrets` key `secret_key`.
3. Optional **Connect** (Stripe Connect): set in connector `config`:

```json
{
  "stripe_account_id": "acct_xxxxxxxx"
}
```

Uses the `Stripe-Account` header on API calls (platform key + connected account).

## v1 actions

| Action | Params |
|--------|--------|
| `stripe.invoices.list` | optional `customer_id`, `status` (`draft`/`open`/`paid`/`uncollectible`/`void`), `limit`, `starting_after` |
| `stripe.subscriptions.get` | `subscription_id` |

### Example

```json
{
  "action": "stripe.invoices.list",
  "params": { "status": "open", "limit": 25 }
}
```

### Agent scopes

| Scope | Actions |
|-------|---------|
| `stripe:invoices:read` | `stripe.invoices.list` |
| `stripe:subscriptions:read` | `stripe.subscriptions.get` |
| `stripe:*` | All of the above |

## Code

- `backend/app/connectors/stripe_api.py`
- `backend/app/services/tool_service.py`
