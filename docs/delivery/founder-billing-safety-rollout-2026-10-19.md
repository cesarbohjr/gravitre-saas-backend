# Founder billing safety rollout

Follow-up to merged PR #505. Adds atomic trial reservations for AI, research and browser voice; legacy voice entry points reject founder trials without a lease. Trial reservations are conservative and span the whole trial; ambiguous calls retain reservations.

Automatic voice top-ups require local and Stripe active paid subscription, explicit opt-in and default payment method, full-pack per-charge cap, monthly cap, and a durable pending barrier. Exactly-once credit validates customer, event, amount, currency and payment identity in a transaction. Ambiguous payments remain pending and require review; reconciliation never retries charges.

Founder grants require an explicit maximum USD promotional value; checkout compares that cap with the actual licensed plan price. Founder UI exposes durable failed-webhook and reconciliation alerts and manual reconciliation. Daily reconciliation is independently gated by BILLING_RECONCILIATION_ENABLED; reports Stripe status drift and historical paid invoice totals without modifying invoices.

Validation: 256 billing tests passed, one existing skip. All 1760 web tests and TypeScript passed. PGlite PostgreSQL validated both migrations, quota, trial auto-charge denial, pending barrier, exactly-once credit, payment mismatch, monthly cap and browser-role denial. Concurrent PostgreSQL acceptance is required in CI.

Production activation remains COMMERCIAL_OFFERS_ENABLED=false pending sandbox Checkout/invoice acceptance and authenticated founder/non-founder UI verification. Current Stripe connector exposes only live mode; no synthetic charges will be placed on real customer accounts. This record does not claim sandbox or authenticated UI acceptance passed.
