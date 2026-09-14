# I4 — Ask Gravitre ↔ Graph + Inspector / Evidence

**Date:** 2026-09-14  
**Status:** SHIPPED (code)

## Delivered

- `IntelligenceAskCommandSurface` — merges `pageContext.suggestedQuestions` + daily briefing
- SSE visualization path unchanged (G4); drives lens/highlight/focus/selection on Overview
- `quality-copy.ts` — human labels for quality flags (no raw `INSUFFICIENT_DATA` in inspector)
- Inspector **edge selection** context (relationship from → to)
- Inspector **pin drawer** via `IntelligenceExperienceProvider` (non-modal when pinned)
- Tests: quality-copy, edge inspector resolution

## Verification

- [ ] Prod: Ask Gravitre answer focuses map nodes (existing G4 battery)
- [ ] Prod: Edge click opens inspector with relationship copy
- [ ] CI: `e2e/intelligence-hub-ui.spec.ts`
