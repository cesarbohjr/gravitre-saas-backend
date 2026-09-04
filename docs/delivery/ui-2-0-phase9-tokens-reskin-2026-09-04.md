# GRAVITRE UI 2.0 — Phase 9 tokens / broader reskin

**Date:** 2026-09-04  
**Branch:** `main`  
**Mode:** Tranche 1 + Tranche 2 on `main` locally — not claiming production deploy

---

## Tranche 1

| Bucket | Action | Status |
|--------|--------|--------|
| REMOVE duplicates | Delete unused `apps/web/styles/globals.css`; remove orphan `AICommandInput` + `LottieAnimation` (+ barrel exports) | Done |
| REFINE motion | Unify `MOTION` in `lib/design-system.ts` with `animations.timing` | Done |
| REFINE status tokens | Add `--status-*` CSS vars + `@theme` bridges; `STATUS` chip classes | Done |
| RESKIN marketing | Chrome + home below-fold zinc/emerald → semantic tokens | Done |
| ADOPT PageHeader | Metrics hub → shared `PageHeader` | Done |

---

## Tranche 2 (approved deferred items)

| Item | Status | Notes |
|------|--------|-------|
| Desktop token bridge | Done | `apps/desktop/src/styles.css` aliases web dark semantic roles; layout unchanged |
| Broader marketing subpages | Done | `scripts/phase9-marketing-semantic-reskin.mjs` — 62 files |
| Connectors PageHeader | Done | `PageHeader` + `NucleoConnector`; honesty soften on “live monitoring” |
| Lucide→Nucleo (phased) | Done (phase 1) | 6 React icons in `components/icons/nucleo/` + semantic map on hub headers |
| WebGL | Done (scoped) | Raw WebGL2 on `/intelligence` only; reduced-motion + offscreen pause; no three.js |

### Honesty notes

1. Footer “All systems operational” → “Product documentation”.  
2. Connectors “Live monitoring active” → “Status from last refresh”.  
3. WebGL is decorative only — not live org topology.  
4. No new prices / Enable toggles / TRAINED claims.  
5. Nucleo copied into repo — never import `~/.nucleo` at runtime.

### Still later (post–Phase 9)

- Remaining sparse zinc utilities on marketing  
- Broader Lucide→Nucleo beyond hub headers  
- Wire `STATUS.*` chip classes into approvals/BO rows  
- Class B drift-guard mutation proof before program closure  
- Shared token package (only if needed)

---

## Verification

| Check | Label |
|-------|-------|
| `tsc --noEmit` | PASS (local) |
| Honesty vitest (model-runtime) | PASS 5/5 (local) |
| Live Class A screenshots | **NOT RUN** |
| Production deploy | **NOT RUN** |

---

## Customer-surface declaration

- **(a)** Honesty softens + deferred items — authorized in UI 2.0 conversation 2026-09-04.  
- **(b)** No scaffold prices/Enable/TRAINED added.
