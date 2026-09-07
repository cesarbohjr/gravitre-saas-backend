# GRAVITRE UI 3.0 — NODUS FULL-MATCH · PHASE 3–4 TOKENS + BRAND

**Date:** 2026-09-06  
**Status:** **IMPLEMENTED (foundation)** — Gate 0 approved; token + brand + fonts landed  
**Prior:** `docs/delivery/ui-3-0-nodus-full-match-gate-0-audit-2026-09-06.md`

---

## Gate 0 decisions (Cesar · 2026-09-06)

| # | Decision | Resolution |
|---|----------|------------|
| 1 | Fonts | **Adopt Inter Display + DM Mono** (web committed mirror; desktop/extension stack + fallback) |
| 2 | Home section order | **Keep Nodus order**; use **real Gravitre logo** (homepage rebuild = next phase) |
| 3 | Theme | **Light-first only** (`forcedTheme="light"`, system/dark disabled) |
| 4 | Vendor tree | **Remain gitignored**; design-critical assets **mirrored under license** into `apps/web/fonts/` |
| 5 | Brand | **Token extraction approved**; Nodus orange `#f17463` → Gravitre green **`#16a374`** |
| 6 | Platforms | One visual SOT across **web app, marketing web, desktop, browser extension, mobile responsive** |

---

## What shipped this phase

### Web (`apps/web`)
- Inter Display TTFs + loaders under `apps/web/fonts/`
- DM Mono via `next/font/google`
- Root layout wires CSS variables; Geist removed
- `globals.css`: Nodus charcoal/gray/brand/shadow/orbit tokens; `--primary` / `--brand` = `#16a374`; white/Nodus-gray canvas
- Theme toggle = light-only (dark/system removed)

### Desktop (`apps/desktop/src/styles.css`)
- Flipped to **light-first** with the same brand / surface tokens as web

### Extension
- `popup.css` + overlay root aligned to brand green + Inter Display stack + Nodus-style shadow

### Vendor policy
- `vendor/nodus-agent-template/` stays in `.gitignore`
- Design match requires copying licensed primitives into the product tree (fonts first; components next phases)

---

## Cross-platform consistency contract

| Token | Value | Surfaces |
|-------|-------|----------|
| `--brand` / `--primary` | `#16a374` | web, desktop, extension |
| `--brand-soft` | `#e0f3ec` | web (+ desktop alias) |
| Canvas | `#ffffff` / `#f9f9f9` / `#f5f5f5` | all light surfaces |
| Type charcoal | `#202020` | body text |
| Borders | `#eaedf1` | all |
| Fonts | Inter Display + DM Mono | web wired; desktop/extension family name + system fallback until font files bundled |
| Theme | Light only | web forced; desktop `color-scheme: light` |

Mobile responsive: inherits web tokens; Nodus breakpoints preserved when marketing sections land.

---

## Explicitly not done yet (next)

1. Marketing homepage = Nodus section order + real Gravitre logo (no fake prices/claims)
2. Port Nodus marketing primitives (navbar, hero, CTA, …)
3. Nucleo pass on product chrome
4. App shell PLATFORM-ADAPT from Nodus material
5. Bundle Inter Display into desktop/extension packages (currently family-name fallback)

---

## Scaffold honesty

**(a)** Gate 0 decisions + brand green + fonts explicitly authorized this conversation.  
No new customer prices, TRAINED badges, Enable toggles, or compliance claims invented.

---

## Evidence (local foundation)

- Fonts present: `apps/web/fonts/inter-display/InterDisplay-*.ttf`
- Layout imports: `apps/web/app/layout.tsx` → `interDisplay` + `dmMono` + `forcedTheme="light"`
- Brand literal: `--color-brand: #16a374` / `--primary: #16a374` in `apps/web/app/globals.css`

**Not claimed:** production redeploy / live visual PASS — foundation only until homepage + shell phases ship and are verified in browser.
