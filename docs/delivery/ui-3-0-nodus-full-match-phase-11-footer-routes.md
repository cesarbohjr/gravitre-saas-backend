# UI 3.0 — Nodus full-match Phase 11 (footer routes + CTA + logo)

**Date:** 2026-09-07  
**Status:** Shipped on `main` (await Vercel redeploy)  
**Prior:** Phase 10 residue audit `67ef1903`

---

## What changed

1. **Shorter black CTAs** — `Button` is `inline-flex w-fit` so footer/header “Put Gravitre to work” no longer stretches full column width.
2. **Footer-linked page bodies** on Nodus chrome (`MarketingPageHero` / `MarketingRails` / `MarketingPageEndCta`):
   - Blog (+ post), Changelog, Docs, Download, Features, Technology, Extension, Privacy, Terms, Security
3. **Gravitre mark in animations** — `LogoSVG` now uses `/images/gravitre-icon-black.png` (green variant when `text-brand`), replacing the Nodus geometric hub in benefits / how-it-works / agentic skeletons / contact.
4. Removed accidental probe/log files that landed in an earlier migration commit.

## Scaffold honesty

**(a)** Explicitly requested: shorter CTAs, Nodus chrome on menu-linked pages, Gravitre logos in designs/animations.  
No new prices, compliance badges, or Enable toggles.

## Evidence

- Code on `main` after Phase 11 commit.
- Live visual **NOT RUN** until Vercel redeploy + browser check of `/blog`, footer CTA width, and home benefits hub mark.
