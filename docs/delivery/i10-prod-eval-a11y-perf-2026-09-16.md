# I10 — Production eval / a11y / perf hardening

**Date:** 2026-09-16  
**Status:** SHIPPED (code) · prod batteries **NOT RUN** this session

## Delivered

### Accessibility
- Graph **List** view: same snapshot topology as the canvas (`accessibleGraphRows`)
- `aria-live` selection announcements on the graph stage
- Pinned inspector drawer uses `useFocusTrap` (Radix already traps when modal)
- Keyboard cycle via InteractionController (arrow keys on canvas)
- Spatial / WebGL / CORE pulses remain off when `prefers-reduced-motion`
- Hover uses CSS rings instead of rebuilding highlight/payload on pointer move

### Performance
- Layout still cached in sessionStorage (I2)
- Clustering threshold unchanged
- Hover no longer invalidates the renderer payload

### Tests
- Mock `GraphRenderer` swap
- Keyboard cycle
- Accessible list projection
- Quality copy never emits raw `INSUFFICIENT_DATA` / `NOT_CONFIGURED`

## Verification

- Local: `vitest run __tests__/intelligence/i10-a11y-perf-hardening.test.ts` — 4 passed @ 2026-09-16T17:56:21Z
- G1/G4/G8 prod battery (`scripts/verify-g8-intelligence-hub-live.py`): **NOT RUN** (no operator live env in this session)
- Prod screenshot: `https://gravitre.app/intelligence` @ 2026-09-16 (session `gravitre-page-audit-9f21`) — 7-tab shell + Overview graph **visible**; I10 List toggle **not on this SHA** (code not pushed)
- WCAG AA token contrast: **INCONCLUSIVE** (no axe scan)

## Not claimed

I10 does not claim the Intelligence experience is production-complete. G8 Learning→map click-through remains **NOT RUN** when no promoted learnings exist.
