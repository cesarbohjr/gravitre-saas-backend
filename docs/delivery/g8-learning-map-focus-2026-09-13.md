# G8 — Learning → Map Focus E2E (Delivery Report)

**Date:** 2026-09-13  
**G8 COMPLETE:** **PARTIAL** — deep link bridge wired; prod verify **NOT RUN**

---

## Objective

Close the loop between the customer Learning hub (G7) and Intelligence Overview map (G4/G5): selecting a learning insight should focus the canonical graph and open contextual inspection.

---

## Shipped

### Deep link contract
- `learning-map-focus.ts` — `learning:{id}` node ids, visualization builder, `/intelligence?lens=learns&focus=…` href

### Learning hub
- `LearningInsightCard` — **View on intelligence map** link per insight

### Overview hub
- Reads `lens` + `focus` search params on load
- Applies G4 map visualization state + G5 satellite selection when graph node exists
- Initializes active lens from deep link (ensures learns graph is fetched)

### Graph helper
- `resolveCanonicalGraphMapNode()` — map canonical graph node id → `MapNode` for inspector

### Tests
- `learning-map-focus.test.ts`

---

## Acceptance (local)

| Check | Status |
|-------|--------|
| Learning card links to overview with learns lens | **CODE** |
| Overview focuses + selects learning node from URL | **CODE** |
| Node ids use `learning:{id}` canonical prefix | **CODE** |
| Prod Learning → map click-through | **NOT RUN** |

---

## Deferred

- Replace URL params with shared client state when navigating in-app without full reload
- Auto-open inspector drawer scroll on mobile
- Bidirectional highlight from map → Learning hub row

---

## Files changed

- `apps/web/lib/intelligence/learning-map-focus.ts` (new)
- `apps/web/lib/intelligence/canonical-graph-topology.ts`
- `apps/web/components/intelligence/learning-insight-card.tsx`
- `apps/web/app/intelligence/page.tsx`
- `apps/web/__tests__/intelligence/learning-map-focus.test.ts` (new)
