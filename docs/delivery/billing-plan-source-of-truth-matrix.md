# Billing plan source of truth + entitlement matrix

Evidence date: 2026-08-07

## Root cause (Phase 0)

| Source | Cesar workspace (`cbbf993b-…`) |
|--------|-------------------------------|
| Stripe subscription `sub_1TtIK9GkcGZTLqrPXl6bqczn` | **Command** — `price_1TbcniGkcGZTLqrPGRwaFxgZ` (`command_monthly`, $299), status `active`, metadata `plan_code=command` |
| `org_billing.plan_code` | `command` |
| `org_billing.stripe_price_id` | **stale Node** — `price_1TbcngGkcGZTLqrPy3N5B60J` (`node_monthly`, $49) |
| `subscriptions.tier` | `command` |

Structural gap: webhook `customer.subscription.updated` updated `plan_code`/`tier` but **did not write `stripe_price_id`**. Overview reconcile only ran when tier looked like node/free or tiers disagreed — so Command+stale-Node-price never self-healed. UI defaulted missing/failed overview to **Node $49 / 500 / 1000**.

Prior fix `9b1d748c` (UI prefer org_billing + reconcile) is on `main`. Entitlements SoT fix `19ec39bc` was **not** on `main` ancestry — `resolve_entitlements` still preferred `subscriptions.tier`.

## Single source of truth (after fix)

```
Stripe subscription items (licensed price)
        │ webhook always writes plan_code + stripe_price_id
        ▼
org_billing.plan_code  ←── canonical product plan
        │
        ├── get_plan_for_org / GET /api/billing /status /auth/me
        ├── resolve_entitlements (aligned)
        └── subscriptions.tier kept in sync (mirror, not independent SoT)
```

## Entitlement matrix (authoritative: `billing_plans` + `DEFAULT_PLANS`)

| Plan | Price (mo) | Workflow runs | AI credits | Workflows | Agents | Envs | Research lookups | Advanced connectors | Approvals | Audit | Versioning | SSO |
|------|------------|---------------|------------|-----------|--------|------|------------------|---------------------|-----------|-------|------------|-----|
| Node | $49 | 500 | 1,000 | 10 | 1 | 1 | 10 | yes | yes | basic | no | no |
| Control | $129 | 2,500 | 5,000 | 40 | 3 | 2 | 60 | yes | yes | basic | yes | no |
| Command | $299 | 10,000 | 15,000 | 120 | 8 | 5 | 200 | yes | yes | full | full | yes |
| Enterprise | custom | custom | custom | custom | custom | custom | 200 | custom | custom | custom | custom | custom |

Enforcement paths must read `get_plan_for_org` / `resolve_entitlements` (now both org_billing-backed), not static frontend catalogs alone.

## Admin plan changes

`POST /api/admin/billing/plan` (platform admin):

- Writes `org_billing.plan_code` + `subscriptions.tier` (same SoT)
- `mode=internal_override` — Gravitre only, audited as override
- `mode=stripe_sync` — also modifies Stripe subscription price
- Audit: `audit_events` action `billing.plan.changed` + `billing_events`

## Monitoring

Golden signals `billing_plan_drift`: samples `org_billing` rows and alerts when configured Stripe price id maps to a different plan than `plan_code`.
