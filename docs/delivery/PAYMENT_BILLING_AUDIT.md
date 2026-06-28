# Gravitre Payment Processing — Full Audit and Hardening (2026-06-28)

## PHASE 1–2 — TRIAL EXPIRY (P0)

### Trial expiry — audit finding

| Check | Result |
|-------|--------|
| `trial_ends_at` stored | **Yes** — `org_billing.current_period_end` (7-day interval from signup trigger `20260529120000_auth_onboarding_bootstrap.sql` L69–111) plus `organizations.settings.billing.trial_ends_at` |
| Backend check on request paths (before fix) | **Confirmed absent** — `compute_app_access()` treated `trialing` as full access forever; no middleware or dependency checked expiry |
| Stripe webhook trial→active/past_due | **Partially wired** — `routers/webhooks/stripe.py` upserts `org_billing.billing_status` from Stripe subscription status on `customer.subscription.updated`, but **no local expiry computation**; card-free trials never transition if user never checks out |
| Frontend upgrade prompt | **Partial** — dismissible trial countdown banner in `app-shell.tsx`; no global 402 handler; no non-dismissible expired-trial banner |

### Root cause

`trial_ends_at` was stored correctly at signup, but **nothing authoritative read it at request time**. `ACCESS_GRANT_STATUSES` included `"trialing"` unconditionally. Stripe webhooks could update status later, but card-free trials could remain `trialing` in DB indefinitely — matching the live revenue leak.

### Fix (implemented)

| Component | Path |
|-----------|------|
| Single source of truth | `backend/app/billing/entitlement_service.py` — `get_org_billing_state()`, `assert_org_not_blocked()`, `PlanRequiredError` (402) |
| Request gating | `backend/app/middleware/billing_gate.py` — path allowlist/denylist middleware on product API routes |
| Billing status API | `routers/billing.py` — returns `trialExpired`, `billingState`, `daysRemainingInTrial` |
| Access flags | `billing/entitlements.py` — `compute_app_access()` delegates expiry to `resolve_billing_state()` |
| Frontend | `trial-expired-banner.tsx`, `upgrade-modal.tsx`, `lib/billing-plan-required.ts`, `fetcher.ts` 402 handler, `app-shell.tsx` |
| Tests | `tests/billing/test_entitlement_service.py`, updated `test_entitlements.py` |

**Authoritative rule:** if `billing_status == trialing` and `trial_ends_at <= now()` → `status=trial_expired`, `is_blocked=true` regardless of Stripe subscription object.

### Live verification

Production curl with an expired-trial org token was **not run** (no `$EXPIRED_TRIAL_TOKEN` in environment). **Local verification: PASS** — 51 billing tests green including expiry computation and 402 shape.

To verify live after deploy:

```bash
curl -X POST https://api.gravitre.app/api/agent-jobs \
  -H "Authorization: Bearer $EXPIRED_TRIAL_TOKEN" \
  -H "X-Org-Id: $EXPIRED_ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"operator_id":"00000000-0000-0000-0000-000000000001","task":"test"}'
# Expect HTTP 402: {"error":"plan_required","subscription_status":"trial_expired",...}
```

---

## PHASE 3 — Payment processing audit

| Area | Finding |
|------|---------|
| Billing model | **Hybrid** — flat tier subscriptions (Node/Control/Command via Stripe Checkout) + optional metered AI usage prices (`billing/stripe.py` `metered_price_id_for_plan`) |
| Checkout | **Stripe Checkout** redirect — `create_checkout_session()` subscription mode with flat + metered line items |
| Customer portal | `create_customer_portal()` for self-serve billing management |
| Webhook endpoint | `POST /api/webhooks/stripe` |
| Signature verification | **Confirmed enforced** — `stripe.Webhook.construct_event()` in `billing/stripe.py` L138–144; 503 if secret missing |
| Webhook idempotency | **Gap (documented)** — no Stripe `event.id` dedup; retries may duplicate `billing_events` rows and re-upsert subscriptions (usually idempotent upsert, but not formally deduped) |
| Events handled | `checkout.session.completed`, `customer.subscription.created/updated/deleted`, `invoice.payment_succeeded/failed`, marketplace checkout via `fulfill_entitlement_from_checkout` |
| Failed payment | **Partially wired** — `invoice.payment_failed` sets subscription `past_due`; **now gates product access** via `entitlement_service` (Phase 6 fix bundled with P0) |

---

## PHASE 4 — Plan selection and payment flow audit

| Check | Result |
|-------|--------|
| Plan required before platform access | **Not enforced at signup** — new users auto-provision with 7-day `trialing` Node plan (`handle_new_user` trigger); full product access during trial |
| Payment method at trial start | **Optional (card-free trial)** — no Stripe customer required until checkout; messaging must say "add payment to continue" not "auto-charge" |
| Signup journey | Sign up → org auto-created → `trialing` for 7 days → **now blocked after expiry** until `/settings/billing` checkout |
| Gaps | Pre-trial access is intentional freemium trial; post-trial leak was the bug (fixed). No forced plan picker before first login. |

---

## PHASE 5 — Entitlement gating audit

| Tier | Limits (from `middleware/entitlements.py` + `billing/service.py`) |
|------|---------------------------------------------------------------------|
| Node | 2 agents, 10 workflows, 5 connectors, 1000 runs/mo |
| Control | 10 agents, 50 workflows, 20 connectors, Meson/custom webhooks/API |
| Command | Unlimited agents/workflows/connectors, SSO |

| Check | Result |
|-------|--------|
| Enforcement consistency | **Partial** — `_check_plan_limits` on marketplace install; `require_limit` on workflow create and operator agents; **not universal** on all connector/oauth paths |
| Error shape | Plan limits return generic 400 `Plan limit reached` — not 402 structured (deferred; separate from P0) |
| Cross-tier leakage | Tier feature gates via `require_tier` / `require_feature` on select routes; **direct API calls to Control-only features from Node tier remain a risk** on unguarded routes — needs route-by-route audit |

---

## PHASE 6 — Fixes applied (this session)

1. **Trial expiry revenue leak (P0)** — `entitlement_service` + billing middleware + frontend 402 UX
2. **Past-due access leak** — `past_due` now `is_blocked=true` (same class as trial expiry)
3. **402 structured response** — preserved through middleware and `http_exception_handler`
4. **Billing status API** — exposes `trialExpired` for shell banner

**Deferred (explicit):**

- Stripe webhook `event.id` dedup table
- Universal plan-limit 402 responses on all resources
- Route-by-route Control/Command feature guard audit

---

## PHASE 7 — Marketplace templates and premium gating

| Area | Finding |
|------|---------|
| `required_connectors` on dept packs | **Present in seed** — `seed_catalog.py` sets connectors per pack (e.g. Marketing `[HUBSPOT, GOOGLE_ANALYTICS]`, RevOps `[HUBSPOT, SALESFORCE]`) |
| Premium pre-install gating | **Already implemented** — `marketplace/entitlements.py` `assert_install_entitlement()` + Stripe checkout for paid assets |
| Gaps | Some individual agents have empty `required_connectors` when they don't use HubSpot; expansion pack content depth varies — not a billing blocker |

No seed changes required for P0 billing hardening; marketplace paid flow reuses existing entitlement table.

---

## pytest

**51 passed** in `tests/billing/` (0 failures). Full suite not re-run in this session; run `pytest backend/tests/ -q` before deploy.

---

## Final verdict

**The trial-expiry revenue leak is closed in code** with authoritative `trial_ends_at` enforcement, middleware gating on product API paths, structured 402 responses, and frontend upgrade UX. **Live production proof requires an expired-trial org curl** after deploy.

Payment processing uses verified Stripe Checkout + webhook signature validation. **Webhook idempotency and universal plan-limit error shapes remain documented gaps.** Marketplace department packs already declare connector requirements and paid assets are gated via existing entitlement checkout — not part of the P0 leak.
