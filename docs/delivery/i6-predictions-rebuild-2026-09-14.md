# I6 — Predictions rebuild

**Date:** 2026-09-14  
**Status:** SHIPPED (code)  
**Depends on:** I1 shell, I4 Ask command surface

## Delivered

- `PredictionsStage` — KPI strip (UNKNOWN≠ZERO) + department filter + topology + card grid
- `BusinessPredictionCard` — what, horizon, confidence, drivers, impact context, evidence, action (no raw status)
- `PredictionRiskOpportunityTopology` — risks left, opportunities right, horizon hub (not OAuth/domain-pack cards)
- `prediction-display.ts` + `prediction-topology.ts` — format, partition, layout (vitest covered)
- Single honest **unscoped** banner via `qualityFlagToCopy("UNSCOPED_PREDICTION")`
- `IntelligenceAskCommandSurface` on Predictions route
- Surface copy updated — removed TRAINED / data_gate scaffold language from page description

## Verification

- Local: **72/72** intelligence vitest PASS (6 new prediction tests)
- [ ] Prod: Predictions page after Railway deploy
- [ ] Prod: Unscoped banner when `UNSCOPED_PREDICTION` in snapshot

## Not in scope (I7+)

Performance outcome attribution flow, Model Studio fold.
