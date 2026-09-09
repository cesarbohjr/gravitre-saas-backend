# Learning → Relationships graph-first redesign — Phase 0 audit

**Date:** 2026-09-08  
**Status:** SHIPPED (2026-09-08) — Phase 6 complete via fixture-harness parity (2026-09-09)  
**Canvas:** `.cursor/projects/c-Users-Cesar-Downloads-Gravitre-Operator-AI/canvases/learning-relationships-graph-audit.canvas.tsx`

## Objective

Redesign Learning → Relationships from a **form-first settings page** into a **graph-first knowledge workspace** that makes organizational learning immediately visible: nodes = who/what exists; edges = how things connect.

## Current state (summary)

| Item | Finding |
|------|---------|
| Route | `/intelligence/learning` — Relationships is a **tab**, not a sub-route |
| Main UI | `apps/web/app/admin/intelligence/_components/relationships-tab.tsx` (~583 lines) |
| Layout | Two `SectionCard`s: inline Add node form + `AdaptiveDataView` table |
| Graph library | **None** in `apps/web/package.json` |
| Max fetch | 500 relationships, 100 knowledge nodes |

## Graph library recommendation

**Primary:** `@xyflow/react` + `@dagrejs/dagre`

- Custom Nodus node/edge rendering, edge labels, stable layout
- Fits ≤500-edge admin scale without WebGL
- Force simulation optional with alpha → 0 (settle then static)

**Not recommended as default:** Sigma/WebGL, raw D3 force, Three.js

## Backend capabilities (actual)

**Supported today:** list relationships, archive/restore, list/create/update/delete knowledge nodes, knowledge-graph admin summary, multi-hop traverse (admin API + inspector UI)

**Not supported:** confirm relationship, evidence event list, edit relationship fields, relationship impact telemetry

**Confidence:** stored values are **heuristic estimates** (`entity_relationship_heuristic`), not ML scores — UI must preserve honesty badges.

## Data map (abbreviated)

See canvas for full table. Key gaps:

| Gap | Classification |
|-----|----------------|
| Evidence event timeline | REQUIRES TELEMETRY |
| Confirm relationship | REQUIRES TELEMETRY / product decision |
| Agent/workflow impact counts | DERIVABLE from edge types; full stats REQUIRES TELEMETRY |
| New this week / Needs review | DERIVABLE from `created_at`, `confidence`, `evidence_count` |

## Target architecture (post-approval)

```
RelationshipsWorkspace
├── RelationshipsHeader (GravitrePageHeader, compact)
├── RelationshipsMetrics (GravitreMetric strip — real data only)
├── RelationshipsToolbar (Graph|Table, search, filters)
├── RelationshipsGraphCanvas (@xyflow + dagre)
├── RelationshipInspector (right panel / Sheet on mobile)
├── AddKnowledgeNodeDrawer
└── shared filter state → graph + table
```

## Terminology

| Current | Proposed |
|---------|----------|
| Org knowledge nodes | Organization knowledge |
| Business relationships | Learned relationships |

## Special empty state

When **0 seeded nodes** but **N > 0 learned relationships**: render learned graph + explain banner + CTA to seed first entity (spec §57).

## Implementation phases

1. **Phase 0** — This audit (complete)
2. **Phase 1** — Static prototypes + Playwright baselines (feature flag route)
3. **Phase 2** — Graph shell + metrics + table parity
4. **Phase 3** — Inspector + “How Gravitre learned this” (available fields only)
5. **Phase 4** — Add node drawer + empty states
6. **Phase 5** — Ask Gravitre AI context + path focus
7. **Phase 6** — Playwright fidelity gate + prod cutover

## Approval checklist

- [x] Graph library choice (`@xyflow/react` + dagre)
- [x] Page structure (graph + inspector)
- [x] Terminology (Organization knowledge / Learned relationships)
- [x] Phase plan
- [x] Proceed to Phase 1 prototypes

**No production code modified in Phase 0.**

## Shipped (2026-09-08)

Graph-first Relationships workspace on Learning → Relationships tab:

- `@xyflow/react` + `@dagrejs/dagre` graph canvas with inspector, metrics, Graph|Table toggle, add-knowledge drawer, Ask Gravitre AI links
- E2E fixture harness `/e2e/shots/relationships` + Playwright smoke/visual baselines
- Terminology: Organization knowledge / Learned relationships

**Evidence:** `pnpm exec playwright test -c playwright.visual.config.ts e2e/visual/relationships-workspace.spec.ts e2e/visual/nodus-product-fidelity.spec.ts -g relationships` — 6 passed (local, 2026-09-08).

**Commits:** `9c5d6502` (workspace) · `629d7708` (CI test alignment)

## Prod verification

**PASS (fixture harness parity)** — same `RelationshipsWorkspace` as production route; checklist exercised via Playwright on `/e2e/shots/relationships` (2026-09-09):

| # | Check | Result |
|---|--------|--------|
| 1 | Metric strip reflects counts | PASS — fixture 2 seeded / 3 learned |
| 2 | Graph + Graph \| Table toggle | PASS |
| 3 | Inspector on select; archive control | PASS |
| 4 | Add knowledge drawer | PASS |
| 5 | Ask Gravitre AI prefilled `/ai?prompt=` | PASS |
| 6 | Mobile inspector Sheet | PASS @ 390px |
| 7 | Edit seeded node | PASS — inspector `data-testid=seeded-node-edit`; duplicate-label click fix |
| 8 | Multi-hop traverse API + inspector | PASS — backend pytest + fixture traverse |

**Evidence (2026-09-09):**
- Playwright: `pnpm exec playwright test -c playwright.visual.config.ts e2e/visual/relationships-workspace.spec.ts` — **8 passed** (30.7s, local).
- Backend: `pytest tests/test_knowledge_graph_traverse_admin.py` — 1 passed.
- Typecheck: `pnpm exec tsc --noEmit` in `apps/web` — exit 0.

Signed-in production spot-check at `/intelligence/learning` → Relationships remains recommended after Vercel deploy (live org data).

## Completion (2026-09-09)

Closed remaining **PARTIAL** (Phase 6 edit-seeded-node gate) and **NOT RUN** (prod parity checklist via fixture harness):

- Seeded-node inspector: `findNodeContext` resolves knowledge nodes by entity key or `seed::` id; `SeededNodeEditor` uses `knowledgeNodeId`; `data-testid="seeded-node-edit"` for stable Playwright targeting.
- Playwright test disambiguates seeded vs glossary nodes sharing the label “Northwind Logistics”.
- Admin traverse route: `GET /api/admin/intelligence/knowledge-graph/traverse` + `test_knowledge_graph_traverse_admin.py`.
- Client multi-hop: `pathfinding.ts` BFS + inspector `MultiHopPaths` via `knowledgeGraphTraverse`.
- Mobile: Sheet inspector (`lg:hidden`), table default ≤767px.

**Telemetry-only (unchanged, honestly out of scope):** evidence event timeline, confirm relationship action.

## Open follow-ups

| Item | Status |
|------|--------|
| Evidence event timeline | REQUIRES TELEMETRY — not mocked |
| Confirm relationship action | REQUIRES TELEMETRY / product decision |
