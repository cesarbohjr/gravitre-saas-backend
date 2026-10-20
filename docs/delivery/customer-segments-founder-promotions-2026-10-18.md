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


## PR #505 hardening update — 2026-10-19

This update supersedes the earlier reservation and UI implementation notes above.

- `reserve_founder_checkout` locks the external commercial profile and grant,
  freezes customer/price/actor, and gives concurrent requests the same attempt.
  Stripe receives a deterministic idempotency key and fixed one-hour expiration.
  Ambiguous attempts are never released on a timeout or reclaimed after Stripe's
  deduplication window. Reserved grants cannot be revoked through the normal UI.
  Reconcile abandoned sessions in Stripe before any operator-approved repair.
- Redemption requires the matching reservation token in signed Stripe metadata.
  One redeemed founder trial per organization is enforced by a partial unique
  index; existing subscriptions and previous Stripe trials block new checkout.
- Trial Checkout attaches only the base licensed price, collects a payment
  method, cancels if the payment method is missing at trial end, and displays
  automatic renewal/cancellation terms. No metered prices are enabled by this
  checkout, including after conversion. Activating overages is a separate,
  explicitly reviewed billing change. Hard per-feature trial usage quotas and
  auto-top-up behavior still require complete sandbox acceptance.
- Stripe `trial_end` populates entitlement expiry. Signed webhook integration
  tests cover trial activation, redemption, duplicate delivery, conversion,
  cancellation, and invalid signature denial without external Stripe requests.
- Founder UI reads the actual offer activation flag, disables issuance while
  gated, displays reserved attempts, and fetches subscription statuses directly
  from Stripe on selection. The backend verifies Stripe customer ownership.
- Local validation: 231 billing tests passed, one existing skip; two additional
  signed lifecycle tests passed; web TypeScript and targeted ESLint passed.
- Isolated Supabase project `hjkvamjlujevuklholeb`: migration applied successfully;
  four concurrent service-role claims returned the same attempt; cross-org,
  changed-price and expired-key-window claims were denied. Both tables have RLS;
  anon/authenticated cannot read, insert, or call the reservation function.
  The branch's inherited migration history reports MIGRATIONS_FAILED, so these
  bounded schema checks do not certify a full staging application deployment.
- Live Stripe read-only reconciliation: 29 subscriptions, 28 incomplete_expired
  and one canceled. No active/trialing subscriptions. Five subscription-linked
  organizations are two internal and three test, consistent with the prior audit.
  Other customer records remain unreviewed. No new Stripe metadata writes,
  coupons, charges, cancellations, or invoice/history modifications were made.

Release gate remains closed until full head CI, staging application / Stripe
sandbox Checkout and invoice tests, trial quotas and production rollout pass.
The current Stripe connector exposes only the live account; Railway OAuth hides
secret values. Production migration and offer activation are not yet performed.
Customer-facing trial controls and terms are explicitly authorized by the user's
PR #505 request; no placeholder prices or product capabilities were introduced.
