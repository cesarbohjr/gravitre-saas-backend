# UI 3.0 — Nodus full-match Phase 10 (residue audit)

**Date:** 2026-09-07  
**Status:** Shipped on `main` (await Vercel redeploy for live marketing chrome)  
**Scope:** Hardening — no new product surfaces; scrub / quarantine leftover template demo content and amber/orange pricing chrome.

---

## Goal

After Phases 5–9, remove residual Nodus/Notus demo residue that could ship as Gravitre product truth:

- Fake prices, testimonials, logo clouds, compliance badge strips
- Gartner / press / investor marks
- “10x” marketing claims
- Theme toggle that could re-enable dark mode
- Orange / amber marketing highlight chrome → brand green `#16a374`

---

## Quarantined (render `null` or empty exports)

| Surface | Path | Why |
|---------|------|-----|
| Template pricing UI | `nodus/pricing.tsx`, `nodus/pricing-table.tsx` | Demo dollars (`$8`/`$12`/`$25`) |
| Template pricing constants | `nodus-constants/pricing.tsx` | Same |
| Testimonials | `nodus/testimonials.tsx`, `nodus-constants/testimonials.ts` | Invented ROI / quotes |
| Logo cloud | `nodus/logo-cloud.tsx`, `nodus-constants/logos.ts` | Fake customer marks |
| Security strip | `nodus/security.tsx` | Unverified CCPA/GDPR/ISO art |
| Careers / founders seed | `nodus-constants/careers.ts`, `founders.ts` | Template filler |
| Mode toggle | `nodus/mode-toggle.tsx` | Light-first only (Gate 0) |
| Gartner marks | `nodus-icons/general.tsx` (`GartnerLogo`, `GartnerLogoText`) | Trademark / unverified claim |

Homepage already uses `HomePricingCta`, `HomeSecurityNote`, `HomeLogoCloudNote` instead of the quarantined blocks. Authorized plans remain `@/lib/pricing-page-data` on `/pricing`.

---

## Scrubbed copy / chrome

- **Benefits** heading: “Making Engineers 10x faster” → “One brain. Clearer operations.” + Gravitre subcopy (`nodus/benefits.tsx`).
- **Tech card** danger tone: orange → rose (not brand coral).
- **Pricing marketing chrome:** Control-tier amber/orange gradients and comparison highlights → `--brand` / `--brand-soft` (`pricing-page-data.ts`, `pricing-cards-grid.tsx`, `pricing-comparison-prices.tsx`, `(marketing)/pricing/page.tsx`).
- **Demo logo files deleted:** `apps/web/public/nodus/logos/*` (press / compliance / fake customer PNGs). Kept `dashboard.png` + `dashboard@3x.png` for hero product stage.

`SHOW_MARKETING_TESTIMONIALS` remains `false` (pricing page fake quotes stay gated).

---

## Intentionally left

- Product-app amber (warnings / approvals) — not Nodus brand orange.
- Integration logos under `/logos/integrations/` — real connector marks for docs.
- Nodus section comments naming the template — engineering provenance only.

---

## Scaffold honesty

**(a)** Residue scrub explicitly authorized as Phase 10 of the Nodus full-match program.  
No new prices, claims, badges, or Enable toggles invented.

---

## Evidence bar

- **Local / code:** Quarantine stubs + green pricing chrome on `main` after this commit.
- **Live PASS:** Requires Vercel redeploy of `main` + browser check of `/`, `/pricing` (no orange highlight strip; no logo-cloud 404s; benefits H1 updated). Until then: **NOT RUN** for production visual.
