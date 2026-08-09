# Plan price increase — voice-included value capture (2026-08-09)

**Decision (authorized this conversation):** Node $49→$59, Control $129→$149, Command $299→$349 (monthly).  
**Grandfather policy:** **Indefinite** — existing Stripe subscriptions keep their current Price objects; new Prices apply to new checkouts only.

## Phase 1 — Price reference inventory (before change)

### Live Stripe Prices (confirmed)

| Lookup key | Price ID | Amount | Product |
|---|---|---|---|
| `node_monthly` | `price_1TbcngGkcGZTLqrPy3N5B60J` | $49 | `prod_UaoQ80elx9j0G4` |
| `node_annual` | `price_1TbcnhGkcGZTLqrPienI3Lyl` | $492/yr ($41/mo) | same |
| `control_monthly` | `price_1TbcnhGkcGZTLqrP0jEnqsWk` | $129 | `prod_UaoQQphgMCvBFK` |
| `control_annual` | `price_1TbcnhGkcGZTLqrPklUxFvRc` | $1284/yr ($107/mo) | same |
| `command_monthly` | `price_1TbcniGkcGZTLqrPGRwaFxgZ` | $299 | `prod_UaoQztHeXuUzhd` |
| `command_annual` | `price_1TbcniGkcGZTLqrPhzsyjkTj` | $2988/yr ($249/mo) | same |

Railway env (pre-change): `STRIPE_PRICE_ID_{NODE,CONTROL,COMMAND}_{MONTHLY,ANNUAL}` → those IDs.

### Code / data references (must update for new list price + checkout)

| Location | Role |
|---|---|
| Railway `STRIPE_PRICE_ID_*` | Checkout / webhook SoT for **new** signups |
| `backend/app/billing/stripe.py` `price_id_for_plan` / `plan_code_for_price` | Resolve checkout + webhook plan mapping |
| `backend/app/routers/webhooks/stripe.py` | Price→plan map |
| `backend/app/config.py` | Settings fields for price IDs |
| `backend/app/billing/service.py` `DEFAULT_PLANS[].price_usd` | Fallback plan catalog list price |
| `public.billing_plans.price_usd` (+ migrations/seed) | DB plan catalog list price |
| `apps/web/lib/plans.ts` `PLAN_CATALOG` | FE SoT for marketing/checkout display |
| `apps/web/lib/pricing-page-data.ts` | Pricing page via `PLAN_CATALOG` |
| `e2e/trial-expiry-billing-flow.spec.ts` | Asserts `$49/$129/$299` on cards |
| `backend/scripts/stripe_seed_prices.py` | Price seeder defaults |

### Leave alone (not platform plan list price)

- Meson scaffolding / retired $49 voice_interface docs
- Marketing pack tier bands $49/$149/$299 (department packs — different product)
- Marketplace asset `$49` copy
- Historical delivery docs

### Grandfather mechanism

1. Create **new** Stripe Price objects (do not mutate amounts on old Prices).
2. Point Railway env checkout vars at **new** Price IDs.
3. Keep old Price IDs in code as `LEGACY_STRIPE_PLAN_PRICE_IDS` so webhooks/drift still map existing subs → node/control/command.
4. Existing customers’ Stripe subscriptions continue billing old `unit_amount` indefinitely.

**Policy (confirmed):** indefinite grandfather — no forced migration window.

## Phase 2 — New Stripe Prices (created live)

| Lookup key | New Price ID | Amount |
|---|---|---|
| `node_monthly` | `price_1U2SQDGkcGZTLqrP1ZTTdpgJ` | $59 |
| `node_annual` | `price_1U2SQtGkcGZTLqrPylFQGJMm` | $588/yr ($49/mo) |
| `control_monthly` | `price_1U2SQOGkcGZTLqrPssKHr0bX` | $149 |
| `control_annual` | `price_1U2SQtGkcGZTLqrPE2cE8JIo` | $1488/yr ($124/mo) |
| `command_monthly` | `price_1U2SQtGkcGZTLqrPRHfZZSEm` | $349 |
| `command_annual` | `price_1U2SQtGkcGZTLqrPKAoonF7g` | $3492/yr ($291/mo) |

Legacy Prices remain active on existing subscriptions (lookup keys transferred to new Prices).

## Live verification (tip `cba33744`)

| Check | Result | Evidence |
|---|---|---|
| API tip | PASS | `GET https://api.gravitre.app/health` → `git_sha=cba337441def633b3782f233edb086901e09366b` |
| Runtime price wiring | PASS | `GET /api/billing/health` tails `node_monthly_tail=1ZTTdpgJ`, `control_monthly_tail=ssKHr0bX`, `command_monthly_tail=RHfZZSEm` |
| New Node checkout | PASS | `cs_live_b1CR0Dc8…` → `price_1U2SQD…` **$59** (`amount_total=5900`) |
| New Command checkout | PASS | `cs_live_b17eG6tv…` → `price_1U2SQt…RHfZZSEm` **$349** (`amount_total=34900`) |
| Existing Cesar Command | PASS (unaffected) | `sub_1TtIK9…` still `price_1Tbcni…PGRwaFxgZ` **$299** |
| DB list prices | PASS | `billing_plans.price_usd` node=59 / control=149 / command=349 |
| Marketing pricing page | PASS | Live `https://gravitre.app/pricing` shows **$59 / $149 / $349** + “Voice included — Text & Dictate in chat” + FAQ “Is voice included, or is it an add-on?” |

**Grandfather policy (final):** indefinite — existing Stripe Price objects unchanged; new Prices only for new checkouts.
