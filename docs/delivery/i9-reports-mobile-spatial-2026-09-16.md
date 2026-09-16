# I9 — Reports, mobile paths, spatial opt-in

**Date:** 2026-09-16  
**Status:** SHIPPED (code)

## Delivered

### Reports
- Templates: Business · Agent · Prediction · Governance
- Saved views stored per org in `localStorage` (template + period only — no invented metrics)
- Scheduled reports: honest **Not set up yet** (no schedule API)
- Composes existing surfaces (outcome flow, prediction cards, agent contribution, quality flags)
- Removed 10-tab pack/admin table dump as the Reports IA

### Mobile
- Overview graph uses focused relationship path cards under 768px
- Expand graph explorer to open the full canvas; does not shrink the desktop graph

### Spatial opt-in
- `SpatialGraphRenderer` (2.5D projection adapter)
- Toolbar **Spatial** toggle; disabled when `prefers-reduced-motion`

## Verification

- Local: i9 vitest (this ship)
- [ ] Prod: Reports templates + mobile paths after Railway deploy

## Not in scope (I10)

Prod batteries, a11y audit, perf profiling.
