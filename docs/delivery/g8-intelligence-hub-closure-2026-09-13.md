# G8 Intelligence Hub — Closure Report (Open Items)

**Date:** 2026-09-13  
**Prod API battery:** `g8-intelligence-hub-live.json` — **PASS**  
**Prod browser UI:** `g8-intelligence-hub-ui-live.json` — **FAIL** (auth `session_expired`; e2e fallback in CI)

---

## Closed with prod evidence

| Item | Verdict | Evidence |
|------|---------|----------|
| **G1** operator-org active agents | **PASS** | Trust org page-context @ `2026-09-14T02:54:36Z` — `Email Campaign Reporting Agent`, `configuredActiveAgents=1`, metrics match roster |
| **G3** KNOWS entity projection | **PASS** (code + API) | `knowledgeEntityTypes` on snapshot; graph `entity:*` nodes; pytest `test_graph_builder_knowledge_entity_types_on_knows_lens` |
| **G3** force-directed layout | **CODE** | `refineLayoutWithForces()` in `map-topology.ts` |
| **G4** SSE map focus | **PASS** | conv `9c8a0477-…` / `59808315-…`; heuristic fallback removed |
| **G5/G7** evidence schema | **PASS** | page-context predictions with `evidence[]` |
| **G6** metrics semantics | **PASS** | `configuredActiveAgents` + `currentlyRunningAgents` |

---

## Remaining honest limits

| Item | Verdict | Why |
|------|---------|-----|
| **G5** prod browser inspector + EvidenceGraphCanvas | **NOT RUN** | Prod login blocked (`session_expired` for fixture/JWT). **CI:** `e2e/intelligence-hub-ui.spec.ts` |
| **G8** Learning → map click-through | **NOT RUN** | No promoted learnings in isolated or operator org snapshots — cannot invent learning rows |
| **G8** prod browser deep link | **NOT RUN** | Same auth blocker + no learning cards |

---

## Scripts

```powershell
python scripts/verify-g8-intelligence-hub-live.py
python scripts/verify-g8-intelligence-hub-ui-live.py   # requires valid prod login or CI e2e
pnpm exec playwright test e2e/intelligence-hub-ui.spec.ts
```

---

## Phase completion status

| Phase | Status |
|-------|--------|
| G1 | **COMPLETE** — trust org PASS + prior user-confirmed PASS |
| G2 | **COMPLETE** (prior) |
| G3 | **COMPLETE** — canonical graph + entity nodes + semantic/force layout + edge types |
| G4 | **COMPLETE** — SSE authoritative; prod PASS |
| G5 | **PARTIAL** — drawer CODE; prod browser NOT RUN; e2e added |
| G6 | **COMPLETE** — prod metrics PASS |
| G7 | **PARTIAL** — hub CODE; prod learnings empty (honest) |
| G8 | **PARTIAL** — deep link CODE; prod click-through NOT RUN (no learnings) |
