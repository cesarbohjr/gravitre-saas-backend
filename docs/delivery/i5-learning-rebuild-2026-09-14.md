# I5 — Learning rebuild

**Date:** 2026-09-14  
**Status:** SHIPPED (code)  
**Depends on:** I1 shell, I4 Ask command surface

## Delivered

- `LearningStage` — segmented views: Learned Recently · Relationships · Memory · Models
- Quality **filters** on Learned Recently (evidence quality, confidence, source, time range) — not a fifth tab
- `learning-filters.ts` — client-side filter logic + vitest coverage
- Relationships segment embeds `RelationshipsWorkspace` (lazy snapshot fetch)
- Memory segment — org knowledge KPIs, entity types, recent auto-promotions sample, link to `/intelligence/memory`
- Models segment — tracked / improved-from-evidence metrics + snapshot model list (honest readiness labels)
- `IntelligenceAskCommandSurface` replaces link-out Ask chips
- Removed from Learning page: `BusinessImpactCard`, `LearningHubLinks`, admin telemetry footer
- Extended `IntelligencePageContextResponse.snapshot` types for `models` + `knowledgeEntityTypes`
- `learning-insight-display` — `learnedAt` preserved for time-range filtering

## Verification

- Local: **66/66** intelligence vitest PASS (includes 3 new filter tests)
- [ ] Prod: Learning page segments render after Railway deploy
- [ ] Prod: Learned Recently filters + View on map (G8) with fresh trace

## Not in scope (I6+)

Predictions rebuild, Performance outcome chain, Model Studio fold.
