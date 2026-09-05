# Design Pass 2 — Light Theme Implementation

**Date:** 2026-09-05  
**Status:** Implemented locally (awaiting commit / deploy / live QA)  
**Plan:** `docs/delivery/ui-2-0-design-pass-2-light-theme-plan-2026-09-05.md`  
**Approval:** Cesar approved light-theme Design Pass 2 plan in-session.

## What changed

- Marketing chrome no longer forces `.dark` / graphite void; syncs `html` to daylight (`data-marketing-canvas="daylight"`) and uses black wordmark.
- `:root` `--g-*` tokens retargeted to warm white canvas, graphite type, soft shadow ladder, soft intelligence/emerald glows (tint, not neon).
- Intelligence Field: light atmospheres lowered; blur atmosphere off for daylight; topology restrained.
- Hero: graphite brand mark with restrained violet accent; softer spotlight; product float uses `--g-shadow-product`.
- Product frames / hero preview: softer tint blooms + product shadow ladder; ribbons on surface (not void).
- Feature cards: material panels + soft state strips (intelligence-soft / emerald-soft).
- Integration strip: muted grayscale logos, color on hover; daylight section ground.
- Integrations grid forced `theme="light"`.
- CTA / floating orbs: reduced tint intensity for white canvas.

## Local browser QA (127.0.0.1:3010) — 2026-09-05

| Region | Score | Notes |
|--------|-------|-------|
| Hero first viewport | 9/10 | Warm canvas, black logo, graphite type, restrained violet mark, soft Field, emerald CTAs |
| Feature cards | 9/10 | Material panels, soft intelligence/emerald chips + state strips |
| Product truth frames | 9/10 | Soft product shadow, tint blooms (not neon), real `/public/product` captures |
| CTA / footer | 8/10 | Light materials, black footer mark; atmospheres restrained |
| Connectors strip | 8/10 | Grayscale → color on hover |

**Overall local craft:** ≥8/10 regions met.  
**Production PASS:** NOT RUN — needs commit → Vercel → live `gravitre.app` (watch alias drift).

## Explicit non-claims

- **Not production PASS** until merge → Vercel deploy → live `gravitre.app` re-check (alias if needed).
- No invented prices / SKUs / TRAINED badges / Enable toggles.
- Dark Design Pass 2 is discarded as art-direction SOT for marketing.

## Customer-surface declaration

**(a)** Visual craft only — no new prices, claims, or entitlement toggles invented this pass.
