# I7 — Performance + outcome attribution

**Date:** 2026-09-16  
**Status:** SHIPPED (code)  
**Depends on:** I1 shell, I4 Ask command surface, canonical page-context

## Delivered

- Interactive **outcome attribution flow** (required): Objective → Signal → Prediction / decision → Agent / workflow → Action → Outcome → Business impact → Learning
- Click any step → inspector with evidence path (unknown steps stay honest, never invented dollars)
- `build_outcome_paths()` on page-context (`outcomePaths`) from snapshot evidence only
- View modes: Business impact · Efficiency · Agent performance · Cost · Reliability
- Compact **agent contribution** cards from existing ROI API (estimates labeled; UNKNOWN ≠ ZERO)
- Removed admin `BusinessImpactCard` KPI dashboard as the Performance hero
- Quality copy for `NO_OUTCOME_ATTRIBUTION`

## Verification

- Local: intelligence vitest + `test_intelligence_outcome_path.py` (run this ship)
- [ ] Prod: Performance page after Railway deploy — click a chain step with a fresh snapshot

## Not in scope (I8+)

Models catalog / Model Studio rebuild.
