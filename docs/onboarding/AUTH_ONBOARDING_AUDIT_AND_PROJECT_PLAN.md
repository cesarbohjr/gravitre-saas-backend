# Gravitre Auth and Onboarding Audit — May 29, 2026

**Project lead:** Cursor (backend + orchestration)  
**Frontend execution:** v0 (detailed prompts below)  
**Success metric:** New user lands on `/get-started` → sees a working AI agent in **under 5 minutes**

---

## Executive summary

Gravitre has strong infrastructure (Supabase auth, Stripe billing, demo seed data, onboarding API) but the **signup funnel optimizes for payment before value**. That blocks activation and revenue.

| Track | Owner | Scope |
|-------|-------|-------|
| **Backend / data / billing** | **Cursor** | Migrations, bootstrap API, billing entitlement logic, demo seed service, webhook fixes, tests |
| **UI / UX / client wiring** | **v0** | `/get-started`, `/login`, `app-shell`, checklist, analytics hooks, metadata |
| **Integration** | **Cursor merges v0 PR → wires API contracts** | Ensure v0 calls backend endpoints exactly as specified |

**Do not start v0 until Cursor ships Phase B API contracts** (or use mocked responses documented below).

---

## Section 1: Current State Assessment

### Sign-up page (`/get-started`) — **4/10**

**File:** `apps/web/app/(marketing)/get-started/page.tsx`

| Element | Finding |
|---------|---------|
| Headline | "Start your journey" — generic, not outcome-driven |
| Subhead | "7-day free trial" — conflicts with payment-before-access |
| OAuth | Google, GitHub, Microsoft — **present above email** ✅ |
| Form fields | Email, password, terms — then **3 more wizard steps** |
| Payment | Stripe checkout **before** Supabase account (email path, lines 173–199) |
| Social proof | None |
| Trust | Terms + Privacy only |
| SEO | No page `metadata`; inherits root title |

### Sign-in page (`/login`) — **6/10**

**File:** `apps/web/app/(marketing)/login/page.tsx`

OAuth primary ✅; raw Supabase `error.message` ❌; no magic link ❌; resend verification ✅.

### Email verification — **7/10**

**File:** `supabase/config.toml` — `enable_confirmations = false` (soft gate). Production may differ.

### Post-auth redirect — **3/10**

**File:** `apps/web/components/gravitre/app-shell.tsx` lines 54–64

Hard gate: `billingStatus !== "active"` → redirect to `/get-started`. OAuth users with org but no Stripe → **loop**.

Email path: public checkout metadata has **no `org_id`** (`backend/app/routers/billing.py` 471–492) → webhook cannot activate billing for new signups.

### Demo data — **2/10**

**File:** `apps/web/lib/supabase/demo-bootstrap.ts` lines 305–307

`ensureDemoDataForOrg` only runs for hardcoded `DEMO_ORGS` UUIDs — **no-ops for real signups**.

### Onboarding — **5/10**

- Backend: `GET/POST /api/onboarding/*` exists (`backend/app/routers/onboarding.py`)
- Frontend checklist: `components/gravitre/onboarding-checklist.tsx` — localStorage only
- `/onboarding` page: 9-step wizard with simulated task — not default post-signup path

### Error messages — **4/10**

Inline errors ✅; human-readable copy ❌ on login and API failures.

### Mobile — **6/10**

Responsive layout ✅; missing `autocomplete` / `type="email"` on some inputs.

### Analytics — **2/10**

`@vercel/analytics` page views only — no funnel events.

---

## Section 2: Conversion Score

| Metric | Value |
|--------|-------|
| **Overall conversion readiness** | **3.5 / 10** |
| **Biggest drop-off** | Payment-before-account + billing gate |
| **Activation time today** | 12–20+ min (OAuth) / broken (email) |
| **Target after project** | **< 5 min** |
| **Estimated lift from P0** | 50–70% signup → first value |

---

## Section 3: Benchmark Gaps (condensed)

| Benchmark | Gap | Fix owner |
|-----------|-----|-----------|
| Slack — magic link, instant access | No magic link; 4-step wizard | v0 login; v0 get-started |
| Linear — OAuth → workspace + sample data | Payment gate; no seed for new orgs | Cursor seed API; v0 app-shell |
| Notion — defer setup questions | Company/plan on signup | v0 collapse wizard |
| Vercel — demo running during signup | Empty dashboard | Cursor bootstrap |
| HubSpot — free tier + checklist | Paid-only gate | Cursor free entitlement; v0 checklist |

---

## Section 4: Split Implementation Plan

### Priority definitions

| Priority | Meaning | Owner |
|----------|---------|-------|
| **P0** | Blocks activation metric | Cursor first, then v0 |
| **P1** | Conversion optimization | v0 primary, Cursor analytics API |
| **P2** | SEO / performance polish | v0 |

---

## PHASE A — Cursor (Backend) — **Start immediately**

### A1. Supabase migration: `handle_new_user` bootstrap (P0)

**New file:** `supabase/migrations/20260529120000_auth_onboarding_bootstrap.sql`

On `auth.users` INSERT:

1. Insert `public.users` row (if not exists)
2. Create `organizations` row — name from `raw_user_meta_data->>'company_name'` or `"My Workspace"`
3. Insert `organization_members` (role `admin`)
4. Insert `org_billing` — `plan_code: 'node'`, `billing_status: 'trialing'`, `trial_ends_at: now() + 7 days`
5. Set `organizations.settings.onboarding.seeded: false`

**Acceptance:** New OAuth or email signup has org + membership + trialing billing without frontend calls.

### A2. Org bootstrap + demo seed API (P0)

**New endpoint:** `POST /api/onboarding/bootstrap`

**File:** `backend/app/routers/onboarding.py`

```json
// Response 200
{
  "org_id": "uuid",
  "seeded": true,
  "agents_created": 2,
  "workflows_created": 1,
  "runs_created": 3,
  "welcome_message": "We've set up a sample AI team..."
}
```

**Behavior (idempotent):**

- If `settings.onboarding.seeded === true` → return `{ seeded: true, ...counts from DB }`
- Else seed:
  - Sales Agent + Marketing Agent (real names/descriptions)
  - 1 workflow: "New Lead → Sales qualifies → Marketing enrolls"
  - 3 completed task runs (sample output)
  - 1 mock connector (HubSpot, status `demo`)
- Set `settings.onboarding.seeded = true`, `settings.onboarding.seeded_at = iso`

**Implementation:** Port logic from `apps/web/lib/supabase/demo-bootstrap.ts` into Python service `backend/app/services/org_seed_service.py` — parameterized by `org_id`, not hardcoded demo UUIDs.

### A3. Entitlement API for frontend gate (P0)

**Extend:** `GET /api/billing/status` (backend + Next proxy)

**New response fields:**

```json
{
  "billingStatus": "trialing",
  "planCode": "node",
  "canAccessApp": true,
  "trialEndsAt": "2026-06-05T00:00:00Z",
  "requiresUpgrade": false,
  "upgradeReason": null
}
```

**Rules:**

| `billingStatus` | `canAccessApp` |
|-----------------|----------------|
| `active`, `trialing`, `free` | `true` |
| `inactive` (new org, no row) | `true` (default trialing from trigger) |
| `cancelled`, `past_due` (grace expired) | `false` |

### A4. Fix public checkout webhook path (P0)

**Files:** `backend/app/routers/billing.py`, `backend/app/routers/webhooks/stripe.py`

For paid upgrades (not required for free activation):

- Accept optional `user_id` in public checkout metadata after account exists
- On `checkout.session.completed` with `signup_flow: public_checkout`: link Stripe customer to existing org or create org if authenticated

### A5. Extend `GET /api/auth/me` (P0)

**File:** `backend/app/routers/auth.py`

Add to response:

```json
{
  "org_id": "uuid",
  "onboarding": {
    "seeded": false,
    "completed_at": null,
    "checklist_dismissed": false
  },
  "billing": {
    "status": "trialing",
    "plan_code": "node",
    "can_access_app": true
  }
}
```

### A6. Tests (P0)

- `test_handle_new_user_creates_org_and_billing`
- `test_bootstrap_idempotent`
- `test_billing_status_can_access_app_trialing`
- `test_billing_status_blocks_cancelled`

### A7. Next.js API proxies (P0)

**Cursor adds/updates:**

- `apps/web/app/api/onboarding/bootstrap/route.ts` → proxy `POST /api/onboarding/bootstrap`
- Update `apps/web/app/api/billing/status/route.ts` to pass through new fields

---

## PHASE B — v0 (Frontend) — **Start after Phase A deployed to staging**

### v0 workflow

1. Open v0 project linked to Gravitre design system (zinc/emerald, Gravitre logo)
2. Run prompts **in order** (B1 → B6)
3. Export to branch `v0/auth-onboarding-p0`
4. Cursor reviews PR: API calls match contracts, no duplicate billing logic

---

### v0 Prompt B1 — Collapse `/get-started` to conversion engine (P0)

```
Redesign apps/web/app/(marketing)/get-started/page.tsx for Gravitre AI Operations Platform.

CONSTRAINTS:
- Keep existing imports: beginOAuthSignIn from @/lib/oauth, useAuth from @/lib/auth-context
- Use Supabase client from @/lib/supabase/client for signUp
- Match marketing layout: white bg, zinc-900 buttons, emerald accents
- Mobile-first, min 48px tap targets

LAYOUT (single step only — remove 4-step wizard):
- Headline: "Build your AI team in minutes"
- Subhead: "Agents that work like employees. No credit card required."
- Trust row: "7-day free trial · SOC2-ready · Cancel anytime"

PRIMARY (top):
[ Continue with Google ]  full width
[ Continue with GitHub ]  full width  
[ Continue with Microsoft ] full width
── or continue with email ──

FIELDS:
- Email (type="email", autocomplete="email", required)
- Password (autocomplete="new-password", show/hide toggle, min 8 chars, strength indicator)
- Terms checkbox linking /terms and /privacy

CTA: "Create free account" — full width, loading spinner when submitting

BEHAVIOR on email submit:
1. Disable button, show loading
2. await supabase.auth.signUp({ email, password, options: { emailRedirectTo: getAuthRedirectUrl('/operator', true) } })
3. On success: POST /api/onboarding/bootstrap (via fetch with session bearer)
4. router.replace('/operator')
5. Brief success toast: "You're in! Setting up your AI team..."

BEHAVIOR on OAuth:
- beginOAuthSignIn(provider, '/operator', true) — NOT back to get-started step 2

ERROR MESSAGES (human, inline, never raw Supabase codes):
- invalid_credentials → "That email and password don't match."
- User already registered → "An account exists. Sign in instead." + link to /login
- Generic → "We couldn't create your account. Try again or use Google."

REMOVE entirely:
- Step 2 company name on signup
- Step 3 plan selection on signup  
- Step 4 completion screen
- Stripe checkout on signup (upgrade happens in-app later)

Add apps/web/app/(marketing)/get-started/layout.tsx with metadata:
title: "Get Started Free — Gravitre AI Operations Platform"
description: "Build your AI team in minutes. No credit card required."
openGraph: title, description, type website

Do NOT change backend files. Assume POST /api/onboarding/bootstrap exists.
```

---

### v0 Prompt B2 — Fix billing gate in app shell (P0)

```
Update apps/web/components/gravitre/app-shell.tsx

CURRENT PROBLEM: billingStatus !== 'active' redirects ALL users to /get-started (infinite loop).

NEW LOGIC:
- Fetch GET /api/billing/status (already via SWR)
- Use response.canAccessApp (boolean) — if true, render app
- If canAccessApp === false AND user authenticated → redirect to /settings/billing?reason=subscription_required
- If no user → redirect to /login
- Show dismissible banner when billingStatus === 'trialing': "You're on a 7-day trial of Node. X days left." with link to /pricing

Keep loading spinner during auth + billing check.
Do not block on billingLoading if canAccessApp is already true from cache.

Add welcome banner component (first login only):
- Read onboarding.seeded from GET /api/auth/me
- If seeded === true and localStorage key gravitre-welcome-dismissed not set:
  Show emerald banner: "Welcome! We've set up a sample AI team. Connect your tools to activate them."
  [Explore agents] → /agents  [Dismiss]
```

---

### v0 Prompt B3 — Rewrite `/login` errors + magic link (P1)

```
Update apps/web/app/(marketing)/login/page.tsx

Keep OAuth buttons primary (Google, GitHub, Microsoft above email form).

Add tab or toggle: "Password" | "Magic link"
Magic link: email only → supabase.auth.signInWithOtp({ email, options: { emailRedirectTo } })
Success message: "Check your inbox — we sent a sign-in link to {email}"

Map Supabase errors to human copy (create AUTH_ERROR_MESSAGES constant):
- Invalid login credentials → "That email and password don't match. Try again or reset your password."
- Email not confirmed → existing resend flow, message: "Confirm your email to continue. We can send another link."
- Too many requests → "Too many attempts. Wait a minute and try again."

Add autocomplete="current-password" on password field.
Post-login: router.replace('/operator') — app-shell handles entitlement.

Loading: disable submit + spinner on button during auth.
```

---

### v0 Prompt B4 — Onboarding checklist wired to backend (P1)

```
Update apps/web/components/gravitre/onboarding-checklist.tsx

Replace localStorage-only state with hybrid:
- On mount: GET /api/onboarding (via onboardingApi.getProgress in @/lib/api.ts)
- Map backend steps to checklist items:
  ✅ Create your account (auto-complete if user exists)
  ○ Connect your first tool → /connectors
  ○ Create your first agent → /agents/new
  ○ Run your first task → /operator
  ○ Set up your first workflow → /workflows
  ○ Invite a teammate → /settings/organizations

On item completion (detect via route + action or manual check):
POST /api/onboarding/complete-step { step_key: 'connect', data: {} }

Show in sidebar widget until all complete OR user dismisses.
Progress: "2 of 6 complete"
Persist dismiss in PATCH organizations.settings.onboarding.checklist_dismissed via settings API

Design: match existing framer-motion collapsible card in sidebar.
```

---

### v0 Prompt B5 — Signup analytics events (P1)

```
Create apps/web/lib/analytics/signup-events.ts

Export trackSignupEvent(name, props?) that calls:
- window.gtag if present
- console.debug in dev
- Optional: POST /api/analytics/events (stub if no backend yet)

Fire events:
- signup_page_viewed (on get-started mount, include utm_source from URL)
- signup_started (first field focus)
- signup_oauth_clicked { provider }
- signup_form_submitted
- signup_completed
- signup_failed { error_type }
- onboarding_bootstrap_started / completed
- onboarding_step_completed { step_key }

Wire into get-started/page.tsx and login/page.tsx and app-shell welcome banner.
Do not block UI on analytics failures.
```

---

### v0 Prompt B6 — Mobile + SEO polish (P2)

> **Full copy-paste prompt:** [`docs/onboarding/v0-prompt-B6.md`](./v0-prompt-B6.md)

```
Polish mobile layout and SEO metadata for Gravitre auth/marketing pages.

FILES: get-started/page.tsx, get-started/layout.tsx, login/page.tsx, login/layout.tsx,
       pricing/page.tsx, public/og-get-started.png

MOBILE (/get-started + /login):
- overflow-x-hidden on root; no horizontal scroll at 390px
- OAuth + inputs + CTAs: min-h-[48px], full width
- py-6 sm:py-12 so headline + first OAuth above fold on iPhone SE
- Footer: Privacy · Terms · Security (text-xs, centered, /privacy /terms /security)
- autocomplete: email, new-password (signup), current-password (login)

SEO:
- get-started/layout.tsx + login/layout.tsx with openGraph + twitter summary_large_image
- OG image: /og-get-started.png (1200×630) — emerald gradient, logo, "Build your AI team in minutes"

PRICING:
- Hero + final CTA: secondary link "Start free — no card required" → /get-started (outline pill)

Do NOT change auth handlers, app-shell, backend, or analytics (B1–B5).
See v0-prompt-B6.md for full acceptance checklist.
```

---

## PHASE C — Cursor integration (after v0 PR)

| Task | Owner |
|------|-------|
| Merge v0 branch, resolve conflicts in get-started | Cursor |
| Verify bootstrap called once post-signup | Cursor |
| E2E smoke: signup → operator → agents visible | Cursor |
| Production: `supabase db push` migration | Manual |
| Stripe: keep checkout for `/pricing` upgrades only | Manual |

---

## Section 5: API Contract Summary (v0 ↔ Cursor)

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/auth/me` | GET | Bearer | User + org + onboarding + billing summary |
| `/api/billing/status` | GET | Bearer | `canAccessApp`, `trialEndsAt`, `planCode` |
| `/api/onboarding/bootstrap` | POST | Bearer | Idempotent demo seed |
| `/api/onboarding` | GET | Bearer | Checklist progress |
| `/api/onboarding/complete-step` | POST | Bearer | Mark step done |

**Frontend must NOT:**

- Create org manually on signup (trigger handles it)
- Gate app on `billingStatus === 'active'` only
- Defer Supabase signUp until after Stripe

---

## Section 6: Post-Fix Verification

- [ ] Email signup → `/operator` in < 60s
- [ ] OAuth signup → `/operator` in < 60s  
- [ ] `/agents` shows Sales + Marketing demo agents
- [ ] Sample workflow runs visible on `/workflows`
- [ ] Trial banner shows, no redirect loop
- [ ] Upgrade path: `/pricing` → Stripe still works
- [ ] Mobile 390px — no scroll, full-width CTAs
- [ ] Funnel events in analytics (dev console minimum)

---

## Section 7: Timeline

| Week | Cursor | v0 |
|------|--------|-----|
| **W1** | A1–A7 backend + migration + tests | Wait for staging API |
| **W1 end** | Deploy staging, share API docs | Start B1, B2 |
| **W2** | Merge v0, integration tests | B3, B4, B5 |
| **W2 end** | Production deploy | B6 polish |
| **W3** | Monitor activation metric, iterate | A/B copy tests |

---

## Final verdict

**Today:** 12–20+ minutes to first agent (or broken email path).  
**After project:** **< 3 minutes** — signup → auto org → bootstrap → demo agents on `/operator`.

**Lead rule:** Cursor owns truth (data, billing, seed). v0 owns pixels (forms, gates, checklist). Neither ships without the API contract above.

---

## Phase A status — COMPLETE (backend)

**Shipped in repo (apply migration to staging/prod manually):**

| Item | Status | Location |
|------|--------|----------|
| `handle_new_user` trigger | ✅ | `supabase/migrations/20260529120000_auth_onboarding_bootstrap.sql` |
| `POST /api/onboarding/bootstrap` | ✅ | `backend/app/routers/onboarding.py` |
| Entitlement fields on billing status | ✅ | `backend/app/routers/billing.py` → `canAccessApp`, `planCode`, `trialEndsAt` |
| Extended `GET /api/auth/me` | ✅ | `backend/app/routers/auth.py` → `onboarding`, `billing` |
| Public checkout org resolution | ✅ | `backend/app/billing/service.py`, webhooks |
| Next.js proxies | ✅ | `apps/web/app/api/onboarding/bootstrap/route.ts`, `apps/web/app/api/billing/status/route.ts` |
| Client API helpers | ✅ | `apps/web/lib/api.ts` → `onboardingApi.bootstrap`, billing status types |
| Tests | ✅ | 12 new tests passing |

**Manual deploy step:**

```bash
supabase db push   # applies 20260529120000_auth_onboarding_bootstrap.sql
```

**v0 is unblocked for Prompts B1 + B2.**
