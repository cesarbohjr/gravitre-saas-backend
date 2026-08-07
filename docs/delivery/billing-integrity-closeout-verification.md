# Billing integrity closeout verification (2026-08-07)

## 1) UI failure never invents Node

**Live FAIL then PASS:**
1. Pre-fix prod tip: Playwright aborted `GET …/api/billing` (`abortedOverview > 0`) and page still painted **Node Plan / $49 / 500 / 1,000**.
2. Vercel deploy of `697a7435` **failed** (TS: `planDirection(..., currentTier | null)`).
3. Fix `97a50c08` unblocked build; Production deploy succeeded on tip including that commit (`84f729db` success @ 2026-08-07T09:15:29Z).
4. **PASS** — `e2e/billing-overview-failure-no-node-default.spec.ts` against `https://gravitre.app` (15.9s): abort count > 0, never `Node Plan`, honest unavailable/loading copy.

## 2) Golden-signals `billing_plan_drift` fires

Disposable org proof (cleaned after):
```text
python scripts/prove-billing-plan-drift-alert.py
# sample_size=2, drift_count=1
# probe_hit: plan_code=command, stripe_price_id=node_monthly → price_maps_to=node
# alert: billing_plan_price_drift>1
# pass: True
```
Org ids used then deleted: `47097eb1-…`, `b33fe479-…`.

## 3) `billing.plan.changed` visible on Audit UI path

- Written via `write_audit_event` for Cesar org with real owner actor  
  `audit_events.id=e5541777-64c1-4b8b-9126-4473eeb77997` @ `2026-08-07T08:23:24Z`
- Dual-write also landed in `audit_logs.id=8e558686-116e-4d59-81ce-e6a9dda65249` (this is what `/api/audit` reads)
- UI surface: **`/audit`** → `formatAuditActionLabel("billing.plan.changed")` = **"Subscription plan changed"** (`apps/web/lib/audit-summary.ts`)

## 4) Bounded webhook partial-update grep

| Handler | Shape | Risk |
|---------|-------|------|
| `webhooks/stripe.py` | Was writing plan without `stripe_price_id`; invoice events updated only `subscriptions` | **Fixed** in `4e6e91e2`. Residual `subscription.deleted` partial write → **fixed in same closeout**: complete terminal state (status canceled/cancelled, plan→node, clear price/sub id); overview no longer invents Trial; UI never defaults missing status to Active |
| hubspot/segment/pagerduty/salesforce inbound | Verify + dispatch; no dual plan-row upserts | No same-class gap |
| `marketplace` checkout fulfill | Updates entitlement checkout session fields | Different domain; not dual SoT plan display |
| Connect `account.updated` | Full status sync from Stripe retrieve | Complete for its fields |

No second unpaid dual-row “plan display” SoT found outside Stripe billing.

## 5) Cancelled Billing & Plan accuracy (`subscription.deleted`)

**Prod confirmation (pre-fix, 2026-08-07):**
- `org_billing.billing_status='cancelled'`: 67 sampled — all `plan_code=node`, all `stripe_subscription_id=null`, **zero** matching `subscriptions` rows, **zero** `subscriptions.status='canceled'`.
- Billing overview path for those orgs **inserted** `tier=free, status=trialing`, so Billing & Plan painted **Node Plan + Trial** (not Canceled). Same family as inventing Active when status is missing (`subscription?.status ?? "active"`).
- No live Command+cancelled row in sample (only one Command org, Cesar, still active). Residual webhook code still left `plan_code`/`tier`/`stripe_price_id` untouched on `customer.subscription.deleted` — a Command cancel would keep paid labels while UI could invent Active/Trial.

**Fix (same closeout):**
- Webhook writes complete terminal state: `canceled`/`cancelled`, plan→`node`, clear price + subscription ids.
- Overview never invents Trial for cancelled orgs; forces `subscription.status=canceled`; exposes `billing_status`.
- UI never defaults missing status to Active; maps `cancelled`→Canceled badge.
- Proof: `python scripts/prove-billing-cancelled-overview.py` + unit tests `test_subscription_deleted_writes_complete_terminal_state`, `test_billing_overview_cancelled.py`.
- Live disposable-org prove (prod DB, local tip handler) @ 2026-08-07: org `98faca66-…` seeded `plan_code=command` + `billing_status=cancelled` → overview returned `subscription.status=canceled`, `billing_status=cancelled`, `pass: True` (cleaned after).
