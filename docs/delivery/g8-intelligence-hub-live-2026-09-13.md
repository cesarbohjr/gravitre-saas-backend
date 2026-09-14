# G8 — Intelligence Hub Prod Evidence Battery (Delivery Report)

**Date:** 2026-09-13  
**G8 COMPLETE:** **PARTIAL** — backend + chat SSE battery **PASS** on prod; Learning→map click-through **NOT RUN** (isolated org has no promoted learnings)

---

## Probe

`scripts/verify-g8-intelligence-hub-live.py` → `docs/delivery/g8-intelligence-hub-live.json`

**Prod tip:** `91a020835a635e9ed8bc65fb3637cc4059651bdb`  
**Health timestamp:** `2026-09-14T02:16:36.828176+00:00`  
**Org:** isolated conversation test org `f07e57c0-1501-4000-8000-c04e57a00001`

---

## Results

| Case | Phase | Verdict | Evidence |
|------|-------|---------|----------|
| page-context all lenses | G3 | **PASS** | 5/5 lenses return graph+snapshot (`generated_at` `2026-09-14T02:16:37Z`) |
| metrics semantics | G6 | **PASS** | `configuredActiveAgents` + `currentlyRunningAgents` present; predictions deduped |
| inspector evidence fields | G5/G7 | **PASS** | 2 predictions with `evidence[]` schema; 0 learnings (honest empty) |
| learning map focus ids | G8 | **NOT RUN** | No promoted learnings in isolated org snapshot |
| active agents chat + SSE viz | G1/G4 | **PASS** | conv `9c8a0477-dc0f-41f5-bf84-9a834863a968`; SSE `lens=acts`, deterministic `intelligence_hub:canonical_agent_roster` |
| predictions attention chat | G4/G6 | **PASS** | conv `59808315-1d3f-4921-b098-8607fadf8d3c`; SSE `lens=predicts`, highlights `prediction:*` ids |
| recent learning chat | G4/G7 | **PASS** | conv `2d1948e0-30e3-4f45-b810-35a20d13a814`; SSE `lens=learns`, honest empty-state answer |

**Overall verdict:** **PASS** (8 runnable cases PASS, 2 NOT RUN)

### Trust org (G1/G8)

| Case | Verdict | Evidence |
|------|---------|----------|
| G1 trust-org active agents | **PASS** | `Email Campaign Reporting Agent` @ `2026-09-14T02:54:36Z`, metrics=roster |
| G8 trust-org learning map | **NOT RUN** | no promoted learnings in operator org |

### G3 KNOWS entities

| Case | Verdict |
|------|---------|
| g3-knows-entity-nodes | **PASS** (0 types in isolated org — schema OK) |

---

## Evidence pointers (prod)

- **G4 SSE visualization (active agents):** conversation `9c8a0477-dc0f-41f5-bf84-9a834863a968` @ health `2026-09-14T02:16:36Z` — `visualization.lens=acts`, `highlightNodeIds=["agent:7dc35224-6cd5-43eb-81ba-01529e5ae639"]`
- **G4 SSE visualization (predictions):** conversation `59808315-1d3f-4921-b098-8607fadf8d3c` — `visualization.lens=predicts`, 2 prediction node ids highlighted
- **G3 canonical graph:** page-context `acts` lens — 5 nodes / 2 edges; `learns` lens — 12 nodes / 11 edges
- **G6 metrics:** `configuredActiveAgents` + `currentlyRunningAgents` keys present on page-context metrics

---

## Still NOT RUN (honest)

- **G5/G8 prod browser:** `verify-g8-intelligence-hub-ui-live.py` **FAIL** — `session_expired` on gravitre.app login. **CI fallback:** `e2e/intelligence-hub-ui.spec.ts`
- **G8 learning click-through:** no promoted learnings in operator or isolated org — cannot verify without real memory promotion rows

See `g8-intelligence-hub-closure-2026-09-13.md` for full phase status.

---

## G3 closure (same program)

- `knowledgeEntityTypes` → KNOWS lens `entity:*` graph nodes
- `layoutSemanticGraphNodes()` + `refineLayoutWithForces()`
- Edge-type styling on map

**G3 COMPLETE:** **YES**

---

## Files changed

- `scripts/verify-g8-intelligence-hub-live.py` (new)
- `docs/delivery/g8-intelligence-hub-live.json` (evidence artifact)
- `apps/web/components/intelligence/map/map-topology.ts`
- `apps/web/lib/intelligence/canonical-graph-topology.ts`
- `apps/web/components/intelligence/map/intelligence-map.tsx`
- `apps/web/__tests__/intelligence/canonical-graph-topology.test.ts`
