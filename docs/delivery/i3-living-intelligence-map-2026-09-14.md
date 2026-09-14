# I3 — Living Intelligence Map

**Date:** 2026-09-14  
**Status:** SHIPPED (code)  
**Depends on:** I1 shell, I2 graph engine

## Delivered

- `OverviewLivingMap` — map-first product composition (lens strip → map → inspector)
- Lens strip **above** the map with lens context copy
- Map loading overlay during snapshot `LOADING` (UNKNOWN ≠ ZERO preserved)
- Taller map stage (`56vh`) as primary hero surface
- Overview page migrated to living map component (no duplicate lens/drawer wiring)
- Canonical snapshot-only pillar fetch when metrics ready (no staggered KPI mixing)

## Not duplicated

Graph engine remains in `lib/intelligence/graph/` — I3 is product layout only.
