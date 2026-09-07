# UI 3.0 — Features page Nodus match

**Date:** 2026-09-07  
**Route:** `/features`

## What changed

Replaced `FeaturesLegacyContent` (old muted bento / app-chrome screens) with the same Nodus building blocks as the homepage:

- `MarketingPageHero` + brand accent + CTAs
- `HeroImage` (dashboard mock + parallax)
- `HowItWorks` (tab animations / skeletons)
- `AgenticIntelligence` (bento + motion skeletons)
- Product surfaces grid from `MARKETING_COPY.homeFeatures`
- Authorized use cases + honest reporting (`MARKETING_COPY.useCases` / `transparencyMetrics`)
- `Benefits` + `HomeSecurityNote` + CTA orbit

## Scaffold honesty

**(a)** Explicitly requested: match homepage / Nodus design standards on `/features`.  
No new prices, compliance badges, Enable toggles, or invented ROI.

## Evidence

- Code on `main` after this commit.
- Live PASS requires Vercel Ready + browser check of `/features` (hero image, how-it-works animations, agentic bento; no legacy “How Gravitre works” muted strip).
