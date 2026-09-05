# Design Pass 2 — Agenforce-Caliber Implementation

**Date:** 2026-09-05  
**Status:** SHIPPED on `main` + live domain re-aliased  
**Governing prompt:** Agenforce-caliber Design Pass 2 (approved)  
**Supersedes:** Conservative Pass 2 plan (not approved)

## Production evidence

| Check | Result |
|-------|--------|
| Commit | `6d750077` (UI) contained in tip `1e0dd947` |
| Domain drift | `gravitre.app` was **not** aliased to latest production — fixed 2026-09-05 via `vercel alias set … gravitre.app` / `www.gravitre.app` → `gravitre-saas-backend-d5efcyy83-gravitre-ai.vercel.app` |
| Live HTML markers | `operating surfaces=True`, `data-marketing-canvas=True`, `product/app-ai=True`, `logo-white=True` @ cache MISS |
| Live browser QA | Dark graphite hero, violet brand mark, emerald CTA, real product capture in hero frame — Cursor browser @ `https://gravitre.app/?qa=dp2` |

**PASS (domain alias + live markers)** — not claiming Lighthouse/perf PASS.

## What shipped

| Area | Change |
|------|--------|
| Tokens | Deeper `--g-void-marketing`, material panel gradient, marketing canvas graphite force |
| Intelligence Field | Atmosphere narrative: intelligence → systems → agents → approval → outcome → balanced |
| Spotlight | CSS MarketingSpotlight (pointer-aware on hero) |
| Hero | Confident type scale, entrance choreography, violet brand mark, emerald CTA material |
| Product preview | Real `/product/*.png` captures, perspective + fade mask, beat-synced STATUS ribbon |
| ProductFrame | Treatments: full / perspective / fade-system / detail / stacked |
| Features | Nucleo icons + material panels + state strips (show-not-tell) |
| Connectors strip | Slow logo cloud marquee + systems atmosphere |
| Homepage | Product-truth section; section atmospheres; CTA balanced violet+emerald |
| Chrome | White logo; `html.dark` + `data-marketing-canvas` sync |
| Desktop | Systems Intelligence Field atmosphere |
| a11y | Reduced-motion fallbacks |

## Visual gap scores (live after alias, 1–10 craft)

| Region | Before (stale light) | After | Notes |
|--------|----------------------|-------|-------|
| Header | 5 | 8 | White logo, emerald CTA |
| Hero | 5 | 8.5 | Void + Field + type + real shot |
| Product truth | 2 | 9 | Real frames, perspective/fade |
| Features | 5 | 8 | Nucleo + state strips |
| Connectors | 5 | 8 | Marquee + systems wash |
| CTA | 6 | 8 | Balanced atmosphere |
| Mobile | — | 7.5 | PARTIAL — needs dedicated pass |

## Stack used (justified)

CSS/tokens · Motion · SVG Field/Signal · Aceternity principles (recreated) · Nucleo · real `/product` shots.  
GSAP / Three.js not added.

## Follow-ups

1. Confirm Vercel production domain auto-assigns on each main deploy (alias drift root cause).
2. Mobile art-direction polish to ≥8.
3. Optional: soft amber approval chip vs yellow chrome perception.
