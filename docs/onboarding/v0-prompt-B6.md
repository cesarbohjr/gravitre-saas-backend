# v0 Prompt B6 — Mobile + SEO polish (P2)

**Prerequisite:** B1 (`/get-started`), B3 (`/login` magic link) already merged. Do not revert auth, bootstrap, or billing gate logic.

**Branch:** `v0/auth-onboarding-b6`  
**Scope:** Frontend only — `apps/web` marketing pages. No backend changes.

---

## Copy-paste prompt for v0

```
Polish mobile layout and SEO metadata for Gravitre auth/marketing pages.

DESIGN SYSTEM (match existing):
- Background: white (get-started) / zinc-50 (login)
- Primary buttons: bg-zinc-900, rounded-xl, min-h-[48px]
- Accents: emerald-600 links, emerald-500 focus rings
- Cards: rounded-2xl border border-zinc-200/80 shadow-xl shadow-zinc-200/40
- Font: existing Geist stack — do not change root layout

FILES TO UPDATE (frontend only):
1. apps/web/app/(marketing)/get-started/page.tsx
2. apps/web/app/(marketing)/get-started/layout.tsx
3. apps/web/app/(marketing)/login/page.tsx
4. apps/web/app/(marketing)/login/layout.tsx  (create if missing)
5. apps/web/app/(marketing)/pricing/page.tsx
6. apps/web/public/og-get-started.png  (1200×630 social preview asset)

Do NOT modify:
- backend/, supabase/, apps/web/app/api/*
- app-shell billing gate (B2)
- onboarding checklist (B4)
- signup-events analytics (B5)
- Auth flows (signUp, signInWithOtp, OAuth handlers)

---

## 1. Mobile polish — /get-started

CONTAINER:
- Root: min-h-screen overflow-x-hidden (prevent horizontal scroll at 390px)
- Outer padding: px-4 py-6 sm:py-12 (CTA above fold on iPhone SE ~667px height)
- Content max-width: max-w-[420px] centered

TOUCH TARGETS:
- All OAuth buttons, inputs, submit: min-h-[48px] full width
- OAuth stack: space-y-3, w-full flex items-center justify-center gap-3

AUTOCOMPLETE (keep if present):
- email → autocomplete="email"
- password → autocomplete="new-password"

FOOTER (below "Already have an account?" link):
- Centered row, text-xs text-zinc-400, flex-wrap gap-x-4
- Links: /privacy (Privacy), /terms (Terms), /security (Security)
- hover:text-zinc-600

VERIFY at 390px width:
- No horizontal scrollbar
- Headline + first OAuth button visible without scrolling
- Footer links wrap cleanly on one or two lines

---

## 2. Mobile polish — /login

CONTAINER:
- Root: min-h-screen overflow-x-hidden bg-zinc-50
- Form column: px-4 sm:px-6 py-6 sm:py-12
- Card padding: p-6 sm:p-8 lg:p-10

Keep existing split layout on lg+ (branding left, form right).
On mobile: hide left branding panel; show logo above "Sign in" heading (lg:hidden).

TOUCH TARGETS:
- OAuth buttons + email/password inputs + submit: min-h-[48px]
- Password toggle remains accessible (44px tap area)

AUTOCOMPLETE:
- email → autocomplete="email"
- password → autocomplete="current-password"

FOOTER (same pattern as get-started):
- Privacy · Terms · Security links centered under "Get started free" link

Do NOT remove Password | Magic link toggle (B3).

---

## 3. SEO — get-started layout

Update apps/web/app/(marketing)/get-started/layout.tsx:

export const metadata: Metadata = {
  title: "Get Started Free — Gravitre AI Operations Platform",
  description: "Build your AI team in minutes. Agents that work like employees, integrations they use as tools. No credit card required.",
  openGraph: {
    title: "Get Started Free — Gravitre AI Operations Platform",
    description: "Build your AI team in minutes. No credit card required.",
    type: "website",
    images: [{ url: "/og-get-started.png", width: 1200, height: 630, alt: "Gravitre — Get started free" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Get Started Free — Gravitre AI Operations Platform",
    description: "Build your AI team in minutes. No credit card required.",
    images: ["/og-get-started.png"],
  },
}

Layout component: export default function GetStartedLayout({ children }) { return children }

---

## 4. SEO — login layout

Create apps/web/app/(marketing)/login/layout.tsx:

export const metadata: Metadata = {
  title: "Sign In — Gravitre AI Operations Platform",
  description: "Access your AI command center. Sign in with Google, GitHub, Microsoft, password, or magic link.",
  openGraph: {
    title: "Sign In — Gravitre AI Operations Platform",
    description: "Access your AI command center.",
    type: "website",
    images: [{ url: "/og-get-started.png", width: 1200, height: 630, alt: "Gravitre" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Sign In — Gravitre AI Operations Platform",
    description: "Access your AI command center.",
    images: ["/og-get-started.png"],
  },
}

---

## 5. OG image — public/og-get-started.png

Create 1200×630 PNG at apps/web/public/og-get-started.png

Visual spec:
- Background: subtle emerald-to-white gradient (matches get-started hero)
- Gravitre wordmark or logo from /images/gravitre-logo-black.png
- Headline text: "Build your AI team in minutes"
- Subline: "No credit card required · 7-day free trial"
- Clean, minimal — no UI mockups, no clutter
- Safe zone: keep text/logo inside center 80% (Twitter crop)

Reference path in metadata only; file must exist in public/.

---

## 6. Pricing — secondary CTA

Update apps/web/app/(marketing)/pricing/page.tsx

A) Hero section (below "Replace hours of work with a single task."):
Add secondary button linking to /get-started:
- Label: "Start free — no card required"
- Style: outline — rounded-full border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-900 hover:bg-zinc-50
- Include ArrowRight icon with subtle hover translate

B) Final CTA section (bottom "Put your work on autopilot"):
Keep primary: "Start your 7-day free trial" (dark pill)
Add secondary beside it on sm+:
- Same label: "Start free — no card required"
- Outline style, stacks below primary on mobile (flex-col sm:flex-row gap-4)

Do not remove existing tier CTAs or billing toggle.

---

## ACCEPTANCE CHECKLIST

Mobile (390px / iPhone SE):
[ ] /get-started — no horizontal scroll
[ ] /get-started — headline + Google OAuth visible above fold
[ ] /login — form usable, OAuth full width
[ ] All interactive elements ≥ 48px height

SEO:
[ ] /get-started has layout.tsx with openGraph + twitter summary_large_image
[ ] /login has layout.tsx with same OG image reference
[ ] og-get-started.png exists at public root

Trust / legal:
[ ] Privacy, Terms, Security footer on get-started and login

Pricing:
[ ] Secondary "Start free — no card required" in hero + final CTA

Regression:
[ ] Email signup + OAuth still work (do not change handlers)
[ ] Magic link toggle still on login
[ ] No backend files touched
```

---

## Cursor merge notes

After v0 exports to branch:

1. Cherry-pick **frontend-only** files — v0 branches sometimes revert backend.
2. Prefer Cursor’s `og-get-started.png` if v0 generates a proper 1200×630 asset; otherwise keep placeholder.
3. Smoke test at 390px in DevTools + share preview for `/get-started` (Twitter card validator optional).

---

## Related

| Item | Doc section |
|------|-------------|
| B1 get-started | AUTH_ONBOARDING_AUDIT_AND_PROJECT_PLAN.md § B1 |
| B3 login magic link | § B3 |
| Full phase plan | AUTH_ONBOARDING_AUDIT_AND_PROJECT_PLAN.md |
