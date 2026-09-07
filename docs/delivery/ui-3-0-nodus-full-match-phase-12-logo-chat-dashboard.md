# UI 3.0 — Nodus full-match Phase 12 (logo scale + chat/dashboard align)

**Date:** 2026-09-07  
**Status:** Shipped on `main` (await Vercel)  

## Changes

1. **LogoSVG** — dense two-bar SVG filling the viewBox (Nodus visual weight). Upsized in benefits hub, how-it-works, agentic chat avatars (`size-5`), contact.
2. **In-app chat colors** — match homepage Nodus chat: blue user bubbles (`bg-blue-500`), gray AI bubbles; white circular AI avatar with larger Gravitre mark; blue user fallback avatar. Functionality unchanged.
3. **Hero dashboard PNGs** — coral/orange chart accents → brand green `#16a374`; Nodus wordmark patched with Gravitre logo (`dashboard.png` / `dashboard@3x.png`).
4. **Auth `/home`** — learning bars + progress footers use brand green (no blue chart fills). Amber kept only for pending approvals.
5. **Marketplace + remaining routes** — Nodus page-shell chrome; shorter CTA padding.

## Scaffold honesty

**(a)** Explicitly requested logo scale, chat color parity, dashboard green bars, full-page Nodus sweep.  
No new prices/claims/Enable toggles. Homepage dashboard mock still shows template demo metrics (128 agents, etc.) as **bitmap illustration only** — live `/home` continues to use real org data only.

## Evidence

- Code commit on `main`.
- Live PASS requires Vercel READY + browser check: home benefits hub mark size, `/ai` blue bubbles, hero dashboard green bars.
