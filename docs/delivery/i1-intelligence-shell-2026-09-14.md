# I1 — Intelligence Shell + State Contract

**Date:** 2026-09-14  
**Status:** SHIPPED (code) — prod verification pending deploy  
**Spec:** `docs/delivery/gravitre-intelligence-experience-rebuild-spec-2026-09-13.md` (Revision 2)

## Delivered

### Permanent Intelligence Experience Shell
- `IntelligenceShell` — single nav, freshness bar, filter slot, command bar slot, page transitions
- `IntelligenceExperienceProvider` in `/intelligence` layout
- `IntelligenceFreshnessBar` — lifecycle-aware freshness display
- `IntelligenceCommandBar` — wraps Ask Gravitre composer

### State contract
- `SnapshotLoadState`: UNINITIALIZED | LOADING | READY | REFRESHING | DEGRADED | ERROR
- `useIntelligenceSnapshot` — canonical `page-context` hook with `keepPreviousData`
- `buildLensMetrics` — UNKNOWN ≠ ZERO; no false zero during load
- Unit tests: `apps/web/__tests__/intelligence/snapshot-state.test.ts` (6 pass)

### IA (7-tab nav)
- Removed **Training** from primary Intelligence hub tabs
- `/training` route preserved; active tab resolves to **Model Studio**
- Removed `LearningSurfacesCallout` from Learning and Models pages
- Model Studio actions: Create · Train · Evaluate · Deploy · Runs

### Pages migrated to shell
Overview, Learning, Predictions, Performance, Reports, Model Studio, Models (`/models`, `/intelligence/models`)

## Not in I1 (next: I2)
- Renderer-agnostic graph engine
- Interactive map (zoom/pan/drag)
- Learning contextual segments (Learned Recently · …)
- Performance outcome flow

## Verification
- [x] Local vitest: snapshot-state.test.ts PASS
- [ ] Prod deploy + Overview lens strip shows `—` during load (not `0`)
- [ ] Hub shows 7 tabs (no Training)
