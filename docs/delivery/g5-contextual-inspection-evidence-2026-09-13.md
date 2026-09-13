# G5 — Contextual Inspection / Evidence Drawer (Delivery Report)

**Date:** 2026-09-13  
**G5 COMPLETE:** **PARTIAL** — drawer + canonical evidence wired; prod live verify **NOT RUN**

---

## Objective

Replace the always-visible empty inspector sidebar with a **rich, contextual evidence drawer** that opens on map selection — integrated with canonical intelligence state and department-scored evidence graphs.

---

## Shipped

### Inspector architecture
- Removed permanent `IntelligenceMapContextPanel` from Overview map row
- Map is **full width**; hint shown when nothing is selected
- **`IntelligenceInspectorDrawer`** — right Sheet, opens on node selection, Esc/backdrop closes

### Canonical context resolver
- `apps/web/lib/intelligence/resolve-inspector-context.ts`
  - Agent: configured-active vs currently-running distinction from canonical snapshot
  - Prediction/signal: confidence, evidence[], qualityFlags, provenance
  - Learning: business statement + evidence from canonical learnings
  - Department: outcome window stats + optional priority evidence match

### Evidence integration
- When department-scored priority data matches a signal/prediction (`useWhyGravitreEvidence`), drawer embeds **`EvidenceGraphCanvas`** + meta — same component as Why panel, now contextual to map selection

### Ask Gravitre bridge
- Inspector **"Ask Gravitre why"** queues a contextual question into `AskGravitreComposer` (`pendingQuestion` prop) and triggers G4 map focus

### Tests
- `apps/web/__tests__/intelligence/resolve-inspector-context.test.ts`

---

## Architecture

```
Map node click / G4 visualization selection
        │
        ▼
resolveInspectorContext(selection, pageContext, whyEvidence)
        │
        ├── facts from canonical snapshot
        ├── evidence[] from CanonicalPrediction / LearningInsight
        ├── qualityFlags
        └── priorityEvidence? → EvidenceGraphCanvas
        │
        ▼
IntelligenceInspectorDrawer (Sheet)
```

---

## Acceptance (local)

| Check | Status |
|-------|--------|
| No permanent empty sidebar | **CODE** |
| Agent inspector shows configured vs running | **CODE** |
| Prediction inspector shows canonical evidence | **CODE** |
| Evidence graph when priority match exists | **CODE** |
| Ask Gravitre why → composer + map focus | **CODE** |
| Prod click-through with evidence rows | **NOT RUN** |

---

## Deferred

- Full objective/workflow/recent-actions timeline (needs richer snapshot fields)
- Drawer on Predictive/Learning sub-routes (Overview only in this slice)
- Retire standalone Why panel (kept below fold as org-wide priority overview)

---

## Files changed

- `apps/web/lib/intelligence/resolve-inspector-context.ts` (new)
- `apps/web/components/intelligence/map/intelligence-inspector-drawer.tsx` (new)
- `apps/web/app/intelligence/page.tsx`
- `apps/web/components/intelligence/ask-gravitre-composer.tsx`
- `apps/web/__tests__/intelligence/resolve-inspector-context.test.ts` (new)

`IntelligenceMapContextPanel` retained for potential reuse; no longer mounted on Overview.
