# Billing browser acceptance — 2026-10-19

## Verified

- Genuine Supabase password sign-in and role boundaries: **2 passed** in [run 39221708183](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/39221708183), commit `69db166c261996bf27c431393aec8ff9813c16c3`, at 08:24 UTC. Organization owner receives 403 on founder account/safety reads and promotional-offer writes. Founder reads both controls, issues a capped trial, and revokes it. Sanitized proof and founder screenshot: `billing-authenticated-roles` artifact 12172675555. These were isolated local Supabase sessions, not production user sessions.
- Real Stripe sandbox recurring invoice `in_1USBECPwmFwcOmL7WUIPpSJw`: paid USD 59.00, `livemode=false`, subscription canceled after verification. [Run 39211761703](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/39211761703), `billing-isolated-acceptance` artifact 12170766076. This invoice assertion passed even though that earlier run's login assertions failed.
- Disposable replay of all 275 migrations passed. Filename reconciliation is isolated in [PR #510](https://github.com/cesarbohjr/gravitre-saas-backend/pull/510); no SQL or production migration-history rows changed.

## Browser harness repair

The existing CSP permits same-origin and HTTPS connections. Direct browser HTTP requests to local Supabase were blocked before a token response. Isolated acceptance now uses the existing same-origin Auth proxy, with a development-only loopback rewrite guarded by `BILLING_ACCEPTANCE_ISOLATED=1`. Production CSP is unchanged. A local config check verified the rewrite is denied in production.

Browser acceptance now selects by billing-related changed files, rather than a one-off branch prefix. Role verification runs before Stripe configuration and uploads its evidence independently. Traces/videos are disabled; credentials and session response bodies are excluded from artifacts.

## Still blocked / not run

Hosted sandbox Checkout, signed-webhook grant redemption/subscription persistence, invoice rendering, and same-org/other-org invoice PDF authorization require repository Actions secrets `STRIPE_TEST_SECRET_KEY` and `STRIPE_TEST_PUBLISHABLE_KEY` from a dedicated sandbox. Neither secret was configured at 08:24 UTC. Anonymous sandbox provisioning became unavailable; CI now fails clearly for missing persistent test credentials instead of repeatedly attempting anonymous provisioning.

Checkout acceptance requires a complete real Stripe test session, a paid zero-value trial invoice, a redeemed grant, a persisted Stripe subscription, licensed-only trial items, billing status, rendered invoice, owner PDF access, and cross-organization PDF denial. These assertions are prepared but **not passed**.

Authenticated production UI acceptance is **NOT RUN**: no usable production browser session was available. Production promotional offers remain disabled. Do not treat the skipped Supabase PR-preview check as production migration acceptance.
