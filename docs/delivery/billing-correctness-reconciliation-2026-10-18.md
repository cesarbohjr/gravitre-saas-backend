# Billing correctness reconciliation — 2026-10-18 UTC

## Production evidence (read-only checks)

- The connected live Stripe account matches the Stripe subscription IDs stored in the production Supabase billing tables.
- All **three** Stripe subscriptions referenced by production `org_billing` are `incomplete_expired` in Stripe and `inactive` in `public.subscriptions`. Do not reactivate, collect, or report meter events for these subscriptions without a new customer-authorized checkout.
- The other **three** locally `active` subscription records have **no Stripe subscription or customer ID**. They are not evidence of a paid Stripe subscription.
- Current-period AI-credit usage: **130** unreported rows / **377** units, split as 127 rows (374 units) for locally active/no-Stripe-subscription orgs; 2 rows (2 units) for inactive/expired Stripe subscriptions; 1 row (1 unit) with no subscription.
- Current-month research usage: **75** unreported rows / 75 units, split as 46 for locally active/no-Stripe-subscription orgs, 28 for inactive/expired Stripe subscriptions, 1 with no subscription. No current-month voice-minute rows appeared in this query.
- Current-month model calls: **0** unsettled calls with an immutable billing contract (`billing_credits IS NOT NULL`), **105** settled calls, and **1,100** legacy/uncontracted calls. A prior count of 53 calls with turn IDs and tokens is a **subset of legacy/uncontracted calls**, **not** a 53-charge recovery backlog.
- `public.stripe_meter_outbox` contains **0** intents.

These counts are snapshots, not proof of invoiceable usage. Unreported usage must not be blindly backfilled into Stripe.

## Correctness invariant

Before a Stripe meter event is staged or claimed, the outbox requires exactly one locally active subscription with a Stripe subscription/customer pair and a successful live Stripe subscription read showing an active/trialing status and matching customer. Missing data, expired subscriptions, identity mismatches, and Stripe read failures all fail closed.

## Operational guardrails

1. Never mark legacy/uncontracted model calls as billable solely because `billing_settled_at` is null.
2. Do not change expired subscriptions to active in Supabase without a verified, customer-authorized Stripe subscription.
3. Do not clear `stripe_reported_at`, replay historic usage, or reset claimed/ambiguous outbox intents without independent Stripe reconciliation.
4. The four billing flags are staged to `true` together; deploy only after CI and review, and monitor the scheduler and outbox for errors.
5. Stripe Sigma was unavailable on the connected account, so this review did **not** certify historical meter-event parity. This release prevents new incorrect meter sends; it does not certify or silently repair past invoices.

## Verification

- Regression tests: `backend/tests/billing/test_stripe_meter_outbox.py`
- Review PR: https://github.com/cesarbohjr/gravitre-saas-backend/pull/503
