# G3 — Semantic Graph Engine (Delivery Report)

**Date:** 2026-09-13  
**G3 COMPLETE:** **PARTIAL** — canonical graph drives map topology; visual renderer polish deferred

---

## Objective

Replace the radial-card map's independent per-lens topology builders with one **canonical IntelligenceGraph** projection (G1), filtered per lens — same nodes/edges, different emphasis.

---

## Shipped

### Backend
- `build_page_context()` now returns **lens-filtered graph** via `filter_graph_for_lens()` (was discarded)

### Frontend
- `apps/web/lib/intelligence/canonical-graph-topology.ts` — maps canonical nodes/edges → `MapTopology`
- `IntelligenceMap` prefers `canonicalGraph` from `pageContext` over legacy `buildMapTopology()`
- Overview hub passes `pageContext.graph` into the map
- New map node kind: `learning` (BookOpen satellite icon)

### Tests
- `canonical-graph-topology.test.ts` (vitest)
- `test_page_context_returns_lens_filtered_graph_not_full_topology` (pytest)

---

## Architecture

```
IntelligenceSnapshot
       │
       ▼
build_intelligence_graph()  ── one graph
       │
       ▼
filter_graph_for_lens(lens) ── page-context view
       │
       ▼
buildTopologyFromCanonicalGraph() ── map render
```

Legacy `buildMapTopology()` remains as fallback when page-context is unavailable.

---

## Deferred (full G3 polish)

- Force-directed / semantic layout beyond radial rings
- Full entity/knowledge nodes on KNOWS lens (requires richer KG projection in snapshot)
- Remove legacy parallel fetches on Overview (G6)
- G4 conversation ↔ map focus via SSE visualization

---

## Files changed

- `backend/app/services/intelligence_projection_service.py`
- `apps/web/lib/intelligence/canonical-graph-topology.ts`
- `apps/web/components/intelligence/map/intelligence-map.tsx`
- `apps/web/components/intelligence/map/map-topology.ts`
- `apps/web/components/intelligence/map/map-satellite-node.tsx`
- `apps/web/app/intelligence/page.tsx`
- `backend/tests/services/test_intelligence_projection_g1.py`
- `apps/web/__tests__/intelligence/canonical-graph-topology.test.ts`
