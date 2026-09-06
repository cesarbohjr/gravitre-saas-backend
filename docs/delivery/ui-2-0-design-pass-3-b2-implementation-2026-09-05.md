# Design Pass 3 — B2 Implementation

**Date:** 2026-09-05  
**Status:** Implemented locally (awaiting commit / deploy / alias)  
**Plan:** `ui-2-0-design-pass-3-agenforce-layout-bold-brand-plan-2026-09-05.md`  
**Approval:** Cesar — **B2 dark shell**; product app keeps light/dark via ThemeProvider.

## What changed

- Marketing chrome forces dark for B2 (`setTheme("dark")`) and **restores** prior `localStorage` theme on unmount so `/app` ThemeToggle still works.
- Bold void canvas tokens (`data-marketing-canvas="void"`) — punchy emerald CTAs, white logos.
- Hero: “One AI brain…” + `HeroBrainFlow` motion + product perspective.
- Progressive narrative sections (problem → brain → pillars → illustrative demo → accountability → stack).
- Animated full-color connector strip.
- Demo labeled **Example scenario** — no fake $ pipeline ROI.

## Theme contract

| Surface | Theme |
|---------|--------|
| Marketing (`MarketingChrome`) | Forced dark while mounted (B2) |
| Product app | `ThemeProvider` light / dark / system via `ThemeToggle` |

## Customer-surface declaration

**(a)** Messaging authorized in conversation.  
**(b)** Demo findings/actions are illustrative UI only — not live metrics.

## Explicit non-claims

Not production PASS until commit → Vercel → live `gravitre.app` (re-alias tip).
