# Founder commercial accounts and promotions — implementation and release gate

## Commercial classification

Commercial identity is stored in `org_commercial_profiles`:
- `external`: independently reviewed external customer.
- `internal`: founder-owned or company-internal account; exclude from external acquisition and MRR.
- `test`: QA, automation and synthetic accounts; exclude from external acquisition and MRR.
- `unreviewed`: default for all unknown organizations. Never count as a customer until reviewed.

The **fourth reporting segment, promotional**, is derived from an **external** account with an available or redeemed founder-issued offer. It is not a fourth permanent identity category. Keep original `external` classification so that customers remain accurately counted after a trial or discount ends. Reporting cohorts: external standard, promotional external, internal, test; show unreviewed separately. Do not sum internal/test or founder charges into external MRR.

Stripe is authoritative for invoice, subscription, payment, coupon and recurring discount state. Supabase keeps the classification, founder grant and audit records, and immutable usage evidence. Trialing is not paying MRR. A promotional customer with a paid invoice contributes its **actual discounted amount** to revenue, not the list price.

## Founder experience

`/admin/commercial` is a founder-only UI with a classification reason, counts, offer creation and revocation. API endpoints are platform-admin-only:
- `GET /api/billing/admin/commercial-accounts`
- `POST /api/billing/admin/customer-segments`
- `POST /api/billing/admin/promotional-offers`
- `POST /api/billing/admin/promotional-offers/{id}/revoke`

Examples:
- 30-day trial: issue `offer_type=trial, trial_days=30`. Authenticated Stripe Checkout creates a 30-day subscription trial and collects a payment method. Do not mistake a trialing subscription for paid revenue.
- 30% off for three months: issue `offer_type=discount, percent_off=30, discount_months=3`. The backend creates a Stripe Coupon with `duration=repeating`, and Checkout applies it to the subscription. The discount applies only to eligible Stripe charges per Stripe coupon rules. Verify metered items and add-ons in staging before live release.
- Founder can choose 1–90 trial days or 1–100% discount for 1–12 months. Each offer is scoped to one external organization, may have a redemption deadline, is recorded and audited, and can be revoked before redemption.
- Checkout only reads a service-role-protected founder grant; client-provided trial lengths or coupon IDs are ignored. The signed checkout webhook consumes the grant idempotently.

## Historical audit classifications

Five evidence-backed organizations are seeded as internal (2) or test (3). All other orgs stay unreviewed until founder classification. No Stripe subscription, invoice or usage records are rewritten.

## Production release checklist (must pass before enabling offers)

1. Review and merge PR with backend, web and migration CI green; fix any test failures. Run a signed Stripe webhook integration test.
2. Apply `supabase/migrations/20261018193000_customer_segments_and_founder_offers.sql` to staging first, then production with an operator-approved migration. Verify grants are inaccessible from `anon` and `authenticated` roles.
3. In Stripe test mode, verify 30-day trial creates `trialing`, 30% discount applies to the correct recurring base plan, redemption is idempotent, and a revoked/expired grant cannot be applied.
4. **Decide and enforce trial overage policy** before enabling live 30-day trials. Metered AI, voice and research charges must not surprise trial users. Recommended: included quota only during trial; block overage or require explicit opt-in.
5. Confirm payment collection timing, trial-ending notifications, refund and coupon semantics, renewal amount and invoice display. Verify public checkout and Payment Element flow do not silently bypass intended offers (only authenticated Checkout currently uses founder grants).
6. Confirm the webhook's checkout completion does not overwrite Stripe's authoritative `trialing` or `incomplete_expired` status. Invoice webhook correction PR #504 must pass and merge independently.
7. Turn on `COMMERCIAL_OFFERS_ENABLED=true` in staging only after migration and tests; keep false in production until sign-off. The default is false. Never enable unrelated billing metering flags as part of this release.

**Status:** code staged in GitHub branch; no live promotions created, no migration applied, no production feature flag activated.


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
