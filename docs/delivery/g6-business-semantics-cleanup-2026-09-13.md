# G6 — Business Semantics Cleanup (Delivery Report)

**Date:** 2026-09-13  
**G6 COMPLETE:** **PARTIAL** — Overview canonical-first; prod verify **NOT RUN**

---

## Objective

Align customer-facing intelligence copy with canonical semantics: business model labels, deduped predictions for attention UI, explicit Acts metric meaning, honest learning empty states, and retire redundant Overview fetches when `page-context` is available.

---

## Shipped

### Business labels
- `apps/web/lib/intelligence/business-labels.ts` — mirrors backend `MODEL_BUSINESS_LABELS`
- Legacy map topology `learns` lens uses business labels instead of raw slugs

### Canonical attention + learning
- `apps/web/lib/intelligence/canonical-attention.ts` — deduped predictions → attention cards; learnings → display rows
- **What needs attention** uses canonical predictions when present (fallback to legacy signals only while page-context loading)
- **What Gravitre learned** shows canonical `LearningInsight` statements with honest empty state

### Lens metrics (Acts / Predicts)
- `build-lens-metrics.ts` — when canonical metrics present: Acts = configured active (not swarm runs); Predicts = deduped count (not catalog artifact count)

### Overview fetch reduction
- Removed parallel `model-catalog` and `training-readiness` SWR on Overview
- Map entity counts from canonical metrics; legacy readiness/catalog props omitted when graph comes from page-context

### Tests
- `business-labels.test.ts`, `canonical-attention.test.ts`

---

## Acceptance (local)

| Check | Status |
|-------|--------|
| Model slugs → business labels on legacy learns lens | **CODE** |
| Attention cards from deduped predictions | **CODE** |
| Acts hint distinguishes configured vs running | **CODE** |
| Learning section honest empty state | **CODE** |
| Prod Overview without duplicate signal nodes | **NOT RUN** |

---

## Deferred

- Remove `useIntelligencePillarsData` knowledgeGraph fetch entirely (coreState still needed for departments)
- Entity-type business labels on KNOWS legacy path
- G7 Learning hub full rebuild off admin snapshot

---

## Files changed

- `apps/web/lib/intelligence/business-labels.ts` (new)
- `apps/web/lib/intelligence/canonical-attention.ts` (new)
- `apps/web/components/intelligence/map/map-topology.ts`
- `apps/web/components/intelligence/map/build-lens-metrics.ts`
- `apps/web/components/intelligence/map/intelligence-support-sections.tsx`
- `apps/web/app/intelligence/page.tsx`
- `apps/web/__tests__/intelligence/business-labels.test.ts` (new)
- `apps/web/__tests__/intelligence/canonical-attention.test.ts` (new)
