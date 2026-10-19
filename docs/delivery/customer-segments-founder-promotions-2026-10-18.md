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

Discount offers create a **real Stripe coupon** with the selected percentage and duration; no local invoice or price manipulation. Founder-issued trials are passed to Stripe Checkout as `subscription_data.trial_period_days`, with payment-method collection. Generic promotion-code entry is disabled: only platform-admin-issued grants are applied at Checkout. Coupons have a one-redemption cap and apply only to licensed base-plan products, not AI, voice, or research overages. The offer cannot be selected or inflated by the end user; it is resolved server-side for the authenticated org.

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
4. Review the implemented founder Commercial accounts UI at `/admin/commercial` (linked from platform intelligence); verify permission denial, category editing, offer creation, revocation, and audit events. Before activation, confirm offer issuance in the UI and expose verified Stripe subscription status alongside account classification.
5. Enable `COMMERCIAL_OFFERS_ENABLED=true` **only after** the above and a production smoke test. Default is false. Existing customer billing must not change until then.
6. Add a reservation/claim step before granting Checkout sessions so a trial grant cannot be used in multiple simultaneous sessions. This is a **release blocker** for automatic trial activation; Stripe discount coupons are limited to one redemption, but trial sessions are not yet reserved atomically.
7. Validate the implemented live Stripe subscription lookup during `checkout.session.completed` for active, trialing, expired and mismatched-customer cases. Verify an offer's end date and post-redemption cohort reporting. Free trials waive the base subscription price, **not necessarily metered overages**; make trial terms and usage caps explicit before release.

No live coupons, charges, refunds, or customer subscription changes are made by this PR.
