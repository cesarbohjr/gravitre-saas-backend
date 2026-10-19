# Stripe authoritative billing reconciliation — 2026-10-18

## Authority model

- Stripe is the source of truth for **Stripe-backed** subscription status, invoice status, payments, credit notes, and metered charges.
- Gravitre is the source of truth for raw, idempotent AI, voice, and research usage evidence, including nonbillable internal and trial usage.
- A local `active` entitlement without a Stripe subscription is **not** proof of a paid Stripe subscription. It may be an internal override or trial and must not be reported as metered Stripe usage without an authorized Stripe subscription.
- Invoice payment events do **not** transition a subscription to `active` or `past_due`. Signed subscription lifecycle events are the authoritative status channel. Previously, late or $0 invoice events could incorrectly reactivate an expired subscription.

## Verified live snapshot

Stripe account `acct_19xPbEGkcGZTLqrP`:
- `sub_1UGnU0GkcGZTLqrPgKnqOqly`: `incomplete_expired`; local subscription `inactive` and org billing `incomplete_expired`.
- `sub_1UJr6vGkcGZTLqrP7kJij9jP`: `incomplete_expired`; local subscription `inactive` and org billing `incomplete_expired`.
- `sub_1UK3j5GkcGZTLqrPZ4lsSohJ`: `incomplete_expired`; local subscription `inactive` and org billing `incomplete_expired`.
- The two remaining locally `active` org billing rows and one `trialing` row have no Stripe subscription or customer ID. **Do not auto-cancel or auto-bill these local entitlements.**
- Invoices for the three Stripe customers: 20 total; 17 `void`, 3 `paid`. The three paid invoices belong to one customer: two paid $299.00 invoices and one $0.00 invoice. These statuses were confirmed directly in Stripe. No evidence was found requiring a credit note, void, refund, or invoice mutation.
- Current-period unreported AI credits: 130 rows / 377 units. Current-month research lookups: 75 rows / 75 units. These remain immutable historical usage evidence, not automatically invoiceable overage.
- The current-month recovery backlog with `billing_credits IS NOT NULL AND billing_settled_at IS NULL` is zero. Legacy/uncontracted model calls are not recoverable customer charges.
- Stripe meter outbox had zero intents at inspection.

## Corrective actions

1. Outbox meter sends fail closed without a verified, active Stripe subscription and matching customer (PR #503, merged).
2. Invoice payment webhook processing no longer changes subscription status; the signed invoice event is still recorded in the audit trail (this PR).
3. **No production invoice changes, status changes, or historical usage rewrites are warranted from the verified data.** Applying changes without an evidenced mismatch would introduce billing inaccuracies.
4. Preserve raw usage and Stripe's finalized invoice history; use adjustments/credit notes for subsequently proven discrepancies rather than rewriting evidence.

## Outstanding acceptance

- Verify the current deployed Railway backend commit and webhook processing.
- Complete a full Stripe meter-event parity check if Stripe reporting access becomes available; Stripe Sigma was unavailable on this connection.
- Keep staged billing flags gated by release checks and ensure any historical backfill is independently reviewed.
