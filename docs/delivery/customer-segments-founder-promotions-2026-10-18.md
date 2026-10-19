# Commercial customer segments and founder offers — implementation / rollout

## Model

Customer **identity** is one of `external`, `internal`, `test`, or `unreviewed`. A promotional offer is an **overlay**, not an identity replacement: an external customer receiving a discount remains an external customer for acquisition and retention metrics. The commercial admin API can display the four business-facing segments: external, internal, test, promotional; unreviewed remains a separate data-quality queue and is excluded from verified external KPIs.

`org_commercial_profiles` is a service-role-only classification registry. `org_promotional_grants` holds a founder-issued, auditable trial or discount offer per organization. Neither table controls subscription/payment truth. Stripe remains authoritative for subscriptions, trial periods, coupons, discounts, payments and invoices.

## Founder controls

Platform admins only:
- `GET /api/billing/admin/commercial-accounts` lists the latest 200 organizations with category and offer history.
- `POST /api/billing/admin/customer-segments` sets an organization's base category with a mandatory reason.
- `POST /api/billing/admin/promotional-offers` assigns either `{"org_id":"...","offer_type":"trial","trial_days":30}` or `{"org_id":"...","offer_type":"discount","percent_off":30,"discount_months":3}`.
- `POST /api/billing/admin/promotional-offers/{grant_id}/revoke` revokes an unused offer.

Discount offers create a **real Stripe coupon** with the selected percentage and duration; no local invoice or price manipulation. Founder-issued trials are passed to Stripe Checkout as `subscription_data.trial_period_days`, with payment-method collection. Stripe Checkout can also accept ordinary Stripe-managed promotion codes on non-grant checkouts. The offer cannot be selected or inflated by the end user; it is resolved server-side for the authenticated org.

This does not create a live promotion by itself. The founder must deliberately issue each grant after rollout.

## Billing/analytics

- External paying customers: category `external` **and** verified active/trialing Stripe subscription, with paid MRR based on Stripe invoices/subscriptions (exclude free trials from paid MRR).
- Founder/internal: excluded from external customer counts, ARR/MRR and conversion denominators.
- Test/QA: excluded from customer, revenue and activation metrics, but retained in test telemetry.
- Promotional: cross-cutting acquisition cohort; report trial conversion, discount redemption, paid conversion, promotional MRR and post-promotion retention separately. Do not sum promotional plus external as disjoint groups.
- Unreviewed: never automatically count as a verified customer.
- Raw historical usage and paid invoices remain immutable.

## Safe rollout

1. Run migrations in staging, then production using normal migration deployment; verify RLS denies direct `anon` and `authenticated` reads/writes.
2. Review seeded founder and QA org classifications; manually classify remaining orgs. Never auto-label every unknown organization as external.
3. Verify CI, Stripe Checkout trials, coupons, webhook redemption, payment method, canceled trial, retry/idempotency, and the existing Payment Element subscription path. The Payment Element path does not support founder offers; promotional customers must use Checkout.
4. Build a founder-only Commercial accounts UI with categories, offers, audit log, Stripe payment status, and an explicit confirmation for issuing coupons/trials.
5. Enable `COMMERCIAL_OFFERS_ENABLED=true` **only after** the above and a production smoke test. Default is false. Existing customer billing must not change until then.
6. Add a reservation/claim step before granting checkout sessions so a grant cannot be used in multiple simultaneous sessions. This is a **release blocker** for automatic promotion activation; signed webhook redemption alone is not sufficient to prevent concurrent redemptions.
7. Reconcile trial state from Stripe before enabling promotional entitlements; `checkout.session.completed` must not independently imply a paid subscription. Also verify whether an offer's end date should be reflected in active-cohort reporting.

No live coupons, charges, refunds, or customer subscription changes are made by this PR.
