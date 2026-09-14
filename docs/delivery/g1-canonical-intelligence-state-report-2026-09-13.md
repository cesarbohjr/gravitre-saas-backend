# G1 — Canonical Intelligence State (Delivery Report)

**Date:** 2026-09-13  
**Deploy tip at close:** `d43f0867` (+ follow-up G1 closure commits pending push)  
**G1 COMPLETE:** **YES** — Active Agent Trust Test **PASS** (user-confirmed + trust-org repro `2026-09-14T02:54:36Z`)

---

## Objective

Establish one canonical backend intelligence projection shared by Intelligence Map, Ask Gravitre, lenses, metrics, and intelligence pages — without a new intelligence database or duplicated source data.

---

## Canonical semantic definitions

| Term | Meaning |
|------|---------|
| **Active agent** | Configured/roster status permits work (`isConfiguredActive`; agents + operators merge) |
| **Running agent** | Currently participating in swarm/workflow execution (`isCurrentlyRunning`) |
| **Active workflow** | Workflow run in `running` status |
| **Action** | Discrete execution event in window (`action_completed`, `workflow_completed`) |
| **Prediction** | Scoped predictive assertion with evidence; deduped by semantic identity |
| **Learning** | Persisted business understanding change (memory promotion evidence — not TTFT/model readiness) |
| **Outcome** | Observed result tied to objective/action/workflow |
| **Improvement** | Measured outcome change per GIBE/outcome events (not model readiness alone) |
| **Knowledge** | Business entities/relationships from knowledge graph |

Source: `backend/app/services/intelligence_semantics.py`

---

## Authoritative source map

| Canonical field | Authoritative source |
|-----------------|----------------------|
| `agents[]` | `agents` table + `operators` roster + swarm runs |
| `predictions[]` | `BusinessSignalsEngine` → dedup |
| `learnings[]` | `MemoryPromotionService` (auto-promoted candidates) |
| `metrics.knowledge` | Knowledge graph admin summary |
| `metrics.execution` | Agent roster + workflow runs + swarm runs |
| `metrics.outcomes` | Outcome learning events (window) |
| `departments[]` | Outcome events aggregation |
| `models[]` | Training readiness (business labels applied) |

Composer: `IntelligenceProjectionService` (`backend/app/services/intelligence_projection_service.py`)

---

## Schemas

| Schema | Path |
|--------|------|
| `IntelligenceSnapshot` | `backend/app/schemas/intelligence_projection.py` |
| `IntelligenceGraph` / nodes / edges | same |
| `IntelligenceMetrics` (typed buckets) | same |
| `LearningInsight` | same |
| `CanonicalPrediction` | same |
| `IntelligencePageContext` (view, not SoT) | same |
| `AssistantVisualization` | same |

---

## Projection architecture

```
Existing authoritative systems
        │
        ▼
IntelligenceProjectionService (45s TTL cache per org/env/window)
        │
        ├── IntelligenceSnapshot
        └── IntelligenceGraph (build_intelligence_graph + filter_graph_for_lens)
                │
        ┌───────┼───────┐
        ▼       ▼       ▼
   page-context  intelligence_hub chat  tool_agent_status
```

---

## Cognitive Runtime integration

- `surface=intelligence_hub` → `compile_intelligence_context_for_query()` scoped context block
- Enriched system prompt passed to streaming (`assistant_system_prompt`)
- Deterministic trust fast-path via `resolve_intelligence_hub_deterministic_answer()` for:
  - Active agents
  - Running agents
  - Predictions needing attention
  - Recent business learning
  - Current activity (configured vs running distinction)
- SSE `visualization` intent on `data-intelligence` events (frontend G4 deferred)

---

## Active Agent Trust Test (§9 — mandatory)

**Question:** "What agents are currently active?"

**Production result:** **PASS** (user-confirmed 2026-09-13)

**Regression lock:** `FORBIDDEN_UNAVAILABLE_AGENT_PHRASES` + pytest in `test_intelligence_projection_g1.py`

Prior failure ("I don't have the current agent status data yet") permanently guarded.

---

## §15 acceptance scenarios

| Scenario | Backend trust path | UI alignment |
|----------|-------------------|--------------|
| Active agents | PASS (prod) | Map + ACTS + chat |
| Running vs configured | Deterministic + metrics | ACTS distinguishes counts |
| Predictions attention | `prediction_trust_answer` + PREDICTS lens | Predictive page → `page-context` |
| Recent learning | `learning_trust_answer` | Admin learning (legacy snapshot); canonical learnings in projection |
| What is Gravitre doing now | `current_activity_trust_answer` | Chat deterministic |
| Improvements | `metrics.outcomes` | Performance page reads canonical outcomes |

---

## Cache & latency

- **TTL:** 45 seconds per `(org_id, environment, window_hours)`
- **Invalidation:** `IntelligenceProjectionService.invalidate(org_id)`
- Projection composes async fetches (KG, signals, outcomes, memory) — typical cost dominated by existing services, not new DB

---

## Remaining inconsistencies (post-G1)

| Gap | Phase |
|-----|-------|
| Learning hub page still uses admin `intelligenceApi.snapshot()` | G7 |
| Map hub still fetches parallel legacy endpoints (model catalog, training readiness) | G6 cleanup |
| Frontend does not yet consume SSE `visualization` for map focus | G4 |
| Radial graph renderer unchanged | G3 (intentionally deferred) |
| `confidence-honesty` lint debt in connector resource adapters | Pre-existing CI |

---

## Tests added

- `backend/tests/services/test_intelligence_projection_g1.py` (16 tests)
- `scripts/cognitive-regression-suite.mjs` G1 structural guards
- Permanent prod regression: `test_prod_active_agent_regression_never_claims_status_unavailable`

---

## Files changed (G1 program)

**Backend:** `intelligence_projection.py`, `intelligence_projection_service.py`, `intelligence_agent_roster.py`, `intelligence_graph_builder.py`, `intelligence_prediction_dedup.py`, `intelligence_context_compiler.py`, `intelligence_semantics.py`, `intelligence_engine.py` (router), `assistant.py`, `assistant_tools.py`, `assistant_sse.py`

**Frontend:** `apps/web/lib/api.ts`, `apps/web/lib/intelligence/canonical-agents.ts`, `apps/web/app/intelligence/page.tsx`, `build-lens-metrics.ts`, `predictive/page.tsx`, `performance/page.tsx`

---

## Do not start yet

- **G2** IA cleanup  
- **G3** Semantic graph engine rebuild  
- **G4** Conversation ↔ visualization  
- **G5–G8** per approved sequence
