# G7 — Learning Rebuilt (Delivery Report)

**Date:** 2026-09-13  
**G7 COMPLETE:** **PARTIAL** — customer Learning hub enriched; prod verify **NOT RUN**

---

## Objective

Rebuild `/intelligence/learning` around canonical business learning — rich insight cards with evidence/provenance, related-surface navigation, and no admin snapshot dependency.

---

## Shipped

### Canonical learning display
- `learning-insight-display.ts` — formats full `LearningInsight` fields for UI
- `LearningInsightCard` — evidence, learned-from, entities, provenance
- Learning page uses `pageContext` only (no `intelligenceApi.snapshot()`)

### Hub enrichment
- Fourth KPI: measured outcomes from canonical metrics
- `LearningHubLinks` — Memory, Outcome reports, Training (labeled honestly)
- Suggested questions from `pageContext.suggestedQuestions` → Ask Gravitre links
- Empty state points to org memory (not training readiness masquerading as learning)

### Tests
- `learning-insight-display.test.ts`

---

## Acceptance (local)

| Check | Status |
|-------|--------|
| Learning page reads canonical learnings only | **CODE** |
| Evidence/provenance on insight cards | **CODE** |
| No admin snapshot API on customer Learning | **CODE** |
| Prod Learning hub with real promoted memory | **NOT RUN** |

---

## Deferred

- In-page relationships graph (admin traverse remains separate)
- Learning → map focus from insight selection (G8 E2E)

---

## Files changed

- `apps/web/lib/intelligence/learning-insight-display.ts` (new)
- `apps/web/components/intelligence/learning-insight-card.tsx` (new)
- `apps/web/components/intelligence/learning-hub-links.tsx` (new)
- `apps/web/app/intelligence/learning/page.tsx`
- `apps/web/__tests__/intelligence/learning-insight-display.test.ts` (new)
