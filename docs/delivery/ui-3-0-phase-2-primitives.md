# GRAVITRE UI 3.0 — PHASE 2 SHARED PRIMITIVES

**Date:** 2026-09-05  
**Status:** **ACCEPTED 2026-09-06** — primitives locked; Phase 3 Hybrid marketing next (in progress / awaiting accept)  
**Prior:** Phase 1 ACCEPTED · Hybrid A+B locked  
**SOT tokens:** [`gravitre-design-system-3.0.md`](./gravitre-design-system-3.0.md)

---

## What landed

| Primitive | Path | Grammar |
|-----------|------|---------|
| `ProductStage` | `apps/web/components/gravitre/visual/product-stage.tsx` | Hybrid A layered / B living beats |
| `StatusChip` | `…/status-chip.tsx` | STATUS tones + optional Pulse |
| `PulseDot` | `…/pulse-dot.tsx` | PULSE |
| `TracePath` | `…/trace-path.tsx` | TRACE |
| `ResolveMark` | `…/resolve-mark.tsx` | RESOLVE (Nucleo `check` icon) |
| Barrel | `…/visual/index.ts` | Re-exports |

**First consumer:** `home-dashboard.tsx` now uses shared `StatusChip` (local chip removed).

---

## Architecture notes

- `ProductFrame` (marketing screenshots) **kept** — `ProductStage` is the composition shell for Hybrid A+B, not a rename.
- Voice (`GravitreOrb` / `Wave` / `VoiceStateVisualizer`) **unchanged** — no forks.
- All new motion respects `useMotionPrefs()` / reduced motion.
- Marketing chrome still **void** — Phase 3 will compose real UI inside `ProductStage` on daylight.

---

## What did **not** change

- No homepage redesign  
- No MarketingChrome theme flip  
- No new dependencies  
- No Playwright goldens  
- No Nucleo full migration wave  
- Premium `PulseRing` / `StatusBeacon` not deleted (legacy; new work should prefer PulseDot / StatusChip)

---

## Accept → next

**ACCEPTED** by Cesar (2026-09-06). Proceed to **Phase 3** Hybrid A+B marketing website (light-first daylight + ProductStage hero).

Visual craft ≥9 for marketing is **not** claimed until Phase 3 screenshot loop.
