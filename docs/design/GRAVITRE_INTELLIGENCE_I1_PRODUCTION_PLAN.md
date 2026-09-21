# Gravitre Intelligence I1 — Harness → Production Plan

**Date:** 2026-09-21  
**Status:** **AUTHORIZED — Phase 1 shipped on `/intelligence` overview** (Cesar 2026-09-21)  
**Prerequisite:** Activity A1 pilot J7 PASS — **met** @ `gravitre.app` deploy `b4f0e32d`  
**Harness reference:** `/dev/ai-workspace-preview?s=intelligence` (I1 + contextual I2)

---

## Objective

Replace the current Intelligence overview map (department/agent décor, quiet five-column evidence) with **I1 Field Topology** — one canonical entity/relationship canvas driven by `IntelligencePageContextResponse`, plus a **collapsible I2 change stream** for WHAT CHANGED / NEEDS ATTENTION / LEARNED / REVIEW.

I3 Matrix Lens remains an advanced concept — not the default.

---

## Production scope (when authorized)

| In scope | Out of scope |
|----------|--------------|
| `/intelligence` overview (`OverviewLivingMap`) | Sub-routes (`/learning`, `/predictive`, etc.) — phase 2 |
| Lens bar → canonical graph emphasis | Full Navigation B shell |
| I2 change stream (collapsible rail) | Marketing autonomous loops |
| Inspector drawer (existing pattern) | Invented graph nodes when entity ids missing |
| Contextual Ask on selection | Wholesale Lucide → Nucleo purge |

---

## Data contract (must not invent)

| Source | Shape |
|--------|--------|
| `GET /api/intelligence/page-context` | `IntelligencePageContextResponse` |
| Graph | `graph.nodes[]`, `graph.edges[]` from `intelligence_graph_builder` |
| Metrics | `knownEntities`, `knownRelationships` from admin summary |
| Relationships | `org_entity_relationships` — source/target entity ids + confidence + evidence |
| Change events | Derive from snapshot `learnings`, `predictions`, quality flags — **no browser-session Set** |

**Sparse entity fix:** When relationship rows exist without resolvable entity ids, show honest empty state (harness `sparse` scene) — do not fabricate nodes.

---

## Implementation sequence

### Phase 0 — Foundation reuse (from Activity A1 pilot)

Extract shared primitives from harness to product package (if not already):

- `apps/web/components/gravitre/visual/topology/` — `TopologyNode`, `TopologyEdge` (from harness `topology-primitives.tsx`)
- Creative grammar: `EvidenceChip`, semantic step tones
- Canvas tokens: `--g-canvas`, `--g-surface-*` (already global)

### Phase 1 — I1 field on overview

1. **`OverviewLivingMap`** — replace hub-centric décor projection with entity/relationship field when canonical graph has usable nodes
2. **`buildTopologyFromCanonicalGraph`** — align node labels (`map-node-labels.ts` truncate/dedupe — already in progress on main)
3. **Lens bar** — filter emphasis on same graph (not separate datasets per lens)
4. **Inspector** — reuse `IntelligenceInspectorDrawer`; wire entity + relationship selection to real ids
5. **Empty/error** — port harness honest copy; link to connectors when graph empty

### Phase 2 — I2 change stream

1. Collapsible left rail — default **closed** (field primary)
2. Events from API: new/changed/confirmed/learned/contradiction/archived/freshness
3. Select event → focus subgraph + open inspector with evidence
4. Mobile: rail → top segmented control or bottom sheet

### Phase 3 — Contextual AI

1. Selection publishes `{ kind: "intelligence_node" | "intelligence_relationship", id, lens }`
2. Single Ask chip in inspector — not duplicated in page header
3. Suggested questions from `pageContext.suggestedQuestions` when present

### Phase 4 — Polish + proof

1. Playwright: extend `gravitre-authenticated-surface-matrix.spec.ts` for I1 markers
2. Journey J6 PASS with lens switch + inspector evidence
3. Responsive 390–1440 matrix
4. Reduced motion static graph transitions

---

## File map (draft)

| Action | Path |
|--------|------|
| Modify | `components/intelligence/pages/overview-living-map.tsx` |
| Modify | `components/intelligence/map/intelligence-graph-stage.tsx` |
| Modify | `lib/intelligence/canonical-graph-topology.ts` |
| New | `components/intelligence/intelligence-change-stream.tsx` |
| New | `components/intelligence/intelligence-field-canvas.tsx` |
| Reuse | `components/intelligence/intelligence-inspector-drawer.tsx` |
| Harness | Keep `/dev/ai-workspace-preview?s=intelligence` as preview until prod PASS |

---

## Before / after (expected)

| Remove | Add |
|--------|-----|
| Department/agent tiles as KG substitute | Entity nodes from canonical graph |
| Cosmetic lens color-only toggles | Lens transforms emphasis on same topology |
| Collapsed five-column evidence footer as primary | Inspector + optional I2 stream |
| Hub orb as default focal point | Relationship edges + learned state hairlines |

---

## Gate checklist (before prod merge)

- [x] Harness I1 + I2 approved (done 2026-09-21)
- [x] Activity A1 J7 PASS with evidence
- [x] Cesar authorizes Intelligence production slice separately (2026-09-21 — Phase 1 overview only)
- [x] No invented nodes when entity ids missing (`overview-field-state.ts` sparse honesty)
- [ ] J6 PASS after I1 deploy (pending post-merge smoke)
- [x] I2 stream default **closed** (field primary)
- [ ] Accessibility: keyboard node select, reduced motion, non-color state (partial — reduced motion on stream rail)

## Shipped (2026-09-21) — Phase 1

| Item | Path |
|------|------|
| I1 field topology surface | `components/intelligence/pages/overview-living-map.tsx` |
| Change events (API-derived) | `lib/intelligence/build-change-events.ts` |
| Sparse/empty honesty | `lib/intelligence/overview-field-state.ts` |
| Map label truncate/dedupe | `lib/intelligence/map-node-labels.ts` |
| Inspector contextual Ask | `components/intelligence/map/intelligence-inspector-drawer.tsx` |
| Vitest | `__tests__/intelligence/build-change-events.test.ts`, `overview-field-state.test.ts` |

---

## Related documents

- `GRAVITRE_3.0_PLUS_CESAR_APPROVAL_PACKAGE.md`
- `GRAVITRE_3.0_HARNESS_REVIEW.md`
- `GRAVITRE_3.0_HARNESS_GATE_STATUS.md`
- `gravitre-creative-product-ui-grammar.md`
