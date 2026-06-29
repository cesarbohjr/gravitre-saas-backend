# v0 prompt — Billing & checkout polish (Payment Element + brand alignment)

Paste into v0 on branch `v0/cesarbohorquezjr-4251-c5e410cc` (sync from `main` after commit `878f9289`). **UI polish only** — backend subscribe API and webhooks are live; extend existing billing components under `apps/web`.

---

## What's already shipped (do not rebuild)

- **Backend:** `POST /api/billing/subscribe` → `{ client_secret, subscription_id, customer_id }` (incomplete subscription + metered line items)
- **Proxy:** `apps/web/app/api/billing/subscribe/route.ts` (Bearer + cookie auth)
- **Checkout page:** `apps/web/app/settings/billing/checkout/page.tsx` — Stripe Payment Element, plan summary, `confirmPayment` → `/settings/billing?status=success`
- **Upgrade paths:** `apps/web/components/billing/upgrade-modal.tsx` and billing page upgrade modal → navigate to `/settings/billing/checkout?plan=…&interval=monthly`
- **Webhooks:** `customer.subscription.*` + `invoice.payment_succeeded` activate entitlements; subscription metadata includes `org_id`, `plan_code`
- **Env:** `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` on Railway (ensure same key on Vercel for Payment Element)

---

## Brand baseline (match production Gravitre)

- **Surfaces:** AppShell, navy/dark-first palette (`#0B0F14` bg, `#11161D` cards), Geist typography, org `--primary` accent
- **Motion:** Framer Motion sparingly; respect `prefers-reduced-motion`
- **Components:** shadcn/ui, existing `premium-effects.tsx` (GlowOrb, MorphingBackground, StatusBeacon) where billing page already uses them
- **Tone:** Enterprise operator console — confident, calm, no marketing fluff on checkout

Read before editing:

- `apps/web/app/settings/billing/page.tsx` (premium billing dashboard — reference for visual language)
- `apps/web/app/settings/billing/checkout/page.tsx` (functional baseline)
- `apps/web/components/billing/upgrade-modal.tsx`
- `apps/web/lib/plans.ts` (Node / Control / Command catalog)

---

## Your task — polish checkout + billing for brand cohesion

### 1. Checkout page (`/settings/billing/checkout`)

Enhance the Payment Element page so it feels like a first-class Gravitre surface, not a bare Stripe embed.

- **Hero layout:** Match billing settings header — subtle gradient backdrop, back link, plan badge (Node / Control / Command), price + interval
- **Order summary card:** Plan name, monthly price, included features (top 3 from `plans.ts`), trial-expired / past-due context line when user arrived from upgrade modal
- **Payment Element container:** Rounded card, consistent border/shadow with billing page; Stripe appearance variables aligned to theme tokens (`--primary`, `--border`, `--card`, `--foreground`)
- **States:** Loading skeleton (not spinner-only), error retry, missing publishable key message styled as inline alert (not raw red box)
- **Trust row:** Lock icon + “Secured by Stripe” + link to billing FAQ; optional “Cancel anytime” subcopy
- **Mobile:** Single column, sticky submit bar on small viewports
- **Dark mode:** Payment Element theme follows site theme (`next-themes`); test both modes

Do **not** change API calls or route structure. Keep `data-testid="payment-element-form"` and `payment-element-submit`.

### 2. Post-payment success (`/settings/billing?status=success`)

- Success state: brief celebratory panel (StatusBeacon active + “You're on {plan}”) before toast-only feedback
- Clear CTA: “Return to Operator” / “Open Assistant” when `canAccessApp` becomes true (poll `billingApi.status()` once after redirect)
- Handle `status=cancelled` if user abandons Payment Element (neutral message, retry link to checkout)

### 3. Upgrade modal alignment

- Visual parity with billing page plan cards (icons, “Most popular”, price typography)
- Headlines by status: trial expired / past due / choose plan — keep existing copy logic
- Secondary link: “Compare plans on billing settings” → `/settings/billing`

### 4. Billing settings page — live data polish (UI only)

Replace obvious placeholders where API data exists:

- **Usage metrics:** Wire to `billingApi.overview()` usage fields when present; keep skeleton → animated counter pattern
- **Payment method card:** Show real last4 / brand from overview if available; “Update card” → Stripe Customer Portal (already wired)
- **Billing history:** Use `billingApi.listInvoices()` list instead of hardcoded `invoices` array; empty state when none
- **Forecast chart:** Only show when real usage series exists; otherwise hide section or show “Usage data will appear after your first billing period”

Do **not** remove premium effects already on the page unless they clash with readability.

### 5. Trial-expired / plan-required UX consistency

Across Operator, Assistant, Swarm, Federation error cards that link to upgrade:

- Ensure “View plans” / upgrade CTA copy matches checkout flow (“Continue to checkout” → `/settings/billing/checkout?plan=control`)
- Banner + modal should not both fight for attention; modal dismiss still allowed

---

## Constraints

- **No new npm dependencies** (Stripe packages already installed)
- **No backend or API contract changes**
- **No hosted Stripe Checkout redirect** for in-app upgrades — stay on Payment Element page
- TypeScript strict; run `pnpm typecheck` in `apps/web`
- List files changed + manual test checklist at end

---

## Manual test checklist (for v0 handoff)

1. Expired trial user → upgrade modal → `/settings/billing/checkout?plan=node` → Payment Element renders
2. Test card `4242…` → success redirect → billing page shows success state → Operator loads without 402
3. Dark + light theme on checkout page
4. Billing page shows real invoices when org has Stripe history
5. Mobile viewport: checkout form usable without horizontal scroll

---

## Sync note

After v0 edits, merge to `main` via existing v0 sync workflow (`docs/integration/V0_BACKEND_SYNC.md`). Cursor should not duplicate v0 layout rewrites — only wire any missing API fields if v0 exposes gaps.
