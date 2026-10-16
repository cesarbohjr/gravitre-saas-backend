# Provider idempotency support matrix (Release 2)

Gravitre may send `Idempotency-Key` on **catalog HTTP** writes when `WRITE_INVOKE_IDEMPOTENCY_ENABLED=true`. That header is **not** treated as provider-native support unless listed below.

| Vendor / transport | Native idempotency | Gravitre behavior when unsupported |
|--------------------|-------------------|-------------------------------------|
| Catalog HTTP (generic) | Unknown per action | Ledger claim + replay; header best-effort only |
| HubSpot / Salesforce / Gmail OAuth executors | Not wired in executor | Ledger claim required before invoke |
| Stripe (billing webhooks) | Separate table | Out of write-invoke ledger scope |

**Safe rule:** Without a documented native key contract for an action, rely on the **Postgres claim ledger** and `uncertain` status — never blind retry after ambiguous delivery.
