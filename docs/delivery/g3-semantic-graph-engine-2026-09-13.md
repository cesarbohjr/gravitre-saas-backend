# G3 — Semantic Graph Engine (Delivery Report)

**Date:** 2026-09-13  
**G3 COMPLETE:** **YES** — canonical graph, KNOWS entity nodes, semantic + force-directed layout, edge-type styling

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

## Shipped (2026-09-13 closure)

- `knowledgeEntityTypes` → `entity:{type}` nodes on KNOWS lens (`intelligence_graph_builder.py`)
- `layoutSemanticGraphNodes()` + `refineLayoutWithForces()` (`map-topology.ts`)
- Canonical edge-type visual styling (`canonical-graph-topology.ts`)
- Prod verify: `g3-knows-entity-nodes` in `g8-intelligence-hub-live.json`

## Deferred

- Per-entity instance nodes (only entity **types** from KG summary today)
- Remove legacy parallel fetches on Overview (partially done in G6)

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
