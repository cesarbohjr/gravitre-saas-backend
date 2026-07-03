# Strategy Bandit v3–v6 — UCB Tables (binding)

Status: **v2 LIVE** · **v3–v6 PLANNED** (spec + acceptance gates; not shipped as separate policy versions).  
Last updated: 2026-07-03.

These tables extend the **tabular bandit ladder** beyond Phase E v2. Each bandit version pairs with the corresponding **Intelligence Engine layer** (v3→v6) and adds richer **UCB context** without neural RL. See [`INTELLIGENCE_ENGINE_V3_V6_TABLES.md`](INTELLIGENCE_ENGINE_V3_V6_TABLES.md) and [`PHASE_E_LONG_HORIZON_SPEC.md`](PHASE_E_LONG_HORIZON_SPEC.md).

---

## Version ladder (summary)

| Version | Name | UCB scope | Primary arms | Intel layer | Status |
|---------|------|-----------|--------------|-------------|--------|
| **v1** | Win-rate ledger | None (exploit only) | `llm:*`, `model:*` | — | **Superseded** |
| **v2** | Org tabular UCB1 | Org-wide + `dept:task` segment | Route, LLM tier, ML model | v7/v8 signals | **LIVE** |
| **v3** | Query-cluster UCB | Per query cluster | Same as v2, segmented by cluster | v3 query clusters | **LIVE** |
| **v4** | Memory-promotion UCB | Per memory category | `memory:promote|suppress|defer:*` | v4 promotion scorer | **PLANNED** |
| **v5** | Retrieval-source UCB | Per connector / rank mode | `source:*`, `rag:hybrid|lexical` | v5 retrieval ranker | **PLANNED** |
| **v6** | Entity-graph UCB | Per entity context | `route:*:graph|no_graph:*` | v6 entity graph | **PLANNED** |

Active policy today: **`bandit_version: v3`** via `StrategyPerformanceLedger.choose_preferred_strategy()` with v2 fallback when cluster segments are under-gated.

---

## UCB core formula (v2 baseline)

All shipped and planned tabular bandits use **UCB1** unless noted:

```
exploitation = wins / (wins + losses)
exploration  = sqrt(2 * ln(N) / n)
ucb_score    = exploitation + exploration
```

| Symbol | Meaning |
|--------|---------|
| `wins`, `losses` | Decided outcomes (`outcome_polarity`) for arm `a` in context `c` |
| `n` | `wins + losses` for arm `a` in context `c` |
| `N` | Total decided trials in the same context pool (org-wide for v2; segment-scoped for v3–v6) |

**v2 selection order** (live in `strategy_performance_ledger.py`):

1. **Exploit:** win-rate beats default by ≥ `0.05` when `decided_samples ≥ 20`.
2. **Explore:** max `weighted_ucb_score` when `decided_samples ≥ 5` and UCB beats default.
3. **Default:** `default_insufficient_evidence`.

**Segment weighting (v2, reused in v3–v6):**

```
weighted_ucb_score = ucb_score * org_learning_profile.segments[segment_key].strategy_weights[arm]
```

Constants: `MIN_SAMPLES_FOR_PREFERENCE = 20`, `MIN_WIN_RATE_DELTA = 0.05`, `MIN_SAMPLES_FOR_UCB = 5`.

---

## v2 reference (live — baseline for v3–v6)

| Dimension | Detail |
|-----------|--------|
| **Purpose** | Org-level strategy selection for LLM tiers and deployed ML models |
| **Policy type** | `tabular_ucb_win_rate` |
| **Storage** | `strategy_performance_records` — `strategy_key`, `segment_key`, `outcome_polarity` |
| **Arms** | `llm:fast|standard|reasoning`, `model:{catalog_name}`, `route:{intent}:...` |
| **Segment key** | `{department}:{intent}` via `parse_segment_key()` |
| **Selection** | `ModelSelector` → `choose_preferred_strategy()` |
| **Recording** | `learning_signal_aggregator`, `intelligence_outcome_coordinator` |
| **Admin API** | `GET /api/admin/intelligence/learning/bandit-status` |
| **Admin UI** | `BanditStatusCard` — Strategy / Wins / Losses / Win rate / **UCB** |
| **Key files** | `strategy_performance_ledger.py`, `model_selector.py`, `rl_policy_gate.py` |

---

## v3 — Query-cluster contextual UCB

| Dimension | Detail |
|-----------|--------|
| **Purpose** | Explore/exploit route and model arms **per query cluster** instead of org-wide pooling |
| **UCB variant** | UCB1 with `N` and `n` scoped to `segment_key = cluster:{id}:{dept}:{task}` |
| **Intel pairing** | Intelligence Engine **v3** — `org_query_clusters`, `QueryClusterer` |
| **Cluster resolution** | Map live query → nearest cluster label at routing time (`knowledge_intelligence_service`) |
| **Arms** | Same as v2 (`llm:*`, `model:*`, `route:*`) — stats partitioned by cluster segment |
| **Min data gate** | Cluster segment must have ≥ `5` decided samples per arm before UCB; ≥ `20` for win-rate exploit |
| **Fallback** | v2 org-wide UCB when cluster unknown or segment under-gated |
| **Storage** | Same `strategy_performance_records`; richer `segment_key` values |
| **Services** | `ModelSelector`, `IntelligenceRouter`, `StrategyPerformanceLedger` |
| **Admin surface** | Bandit status grouped by cluster (future column on Overview) |
| **Status** | **LIVE** — cluster segment wiring shipped with v2 fallback |
| **Key files** | `learning_strategy_keys.py`, `knowledge_intelligence_service.py`, `strategy_performance_ledger.py` |

### v3 UCB context flow

```
user query
  → cluster assignment (v3 QueryClusterer / org_query_clusters)
  → segment_key = cluster:{cluster_id}:{dept}:{intent}
  → rank arms with UCB1(N_segment, n_arm)
  → fallback to v2 if segment under-sampled
```

### v3 acceptance criteria

- [x] `parse_segment_key` accepts optional `query_cluster_id` from classification
- [x] Outcome recording writes cluster-scoped `segment_key`
- [x] `choose_preferred_strategy` tries cluster segment first, then v2 pool
- [x] Admin bandit table shows cluster segment breakdown when data exists

---

## v4 — Memory-promotion arm UCB

| Dimension | Detail |
|-----------|--------|
| **Purpose** | Learn which **memory promotion paths** (approve / suppress / defer) maximize downstream win-rate |
| **UCB variant** | UCB1 over promotion strategy arms per `{dept}:{memory_category}` |
| **Intel pairing** | Intelligence Engine **v4** — `MemoryPromotionScorer`, `memory_promotion_candidates` |
| **Arms** | `memory:promote:{category}`, `memory:suppress:{category}`, `memory:defer:{category}` |
| **Outcome signal** | Post-promotion retrieval wins/losses from `response_evaluation_service` + user feedback |
| **Min data gate** | ≥ `15` resolved promotion decisions per category (matches v4 scorer gate) |
| **Human gate** | Promotion still requires admin approve/reject — bandit ranks queue only |
| **Fallback** | v4 rule-based scorer thresholds when UCB segment under-gated |
| **Storage** | `strategy_performance_records` with `strategy_family: memory_promotion` |
| **Services** | `memory_promotion_service`, `StrategyPerformanceLedger`, `memory_promotion_scorer` |
| **Admin surface** | Memory Promotion tab — promotion UCB rank column (future) |
| **Status** | **PLANNED** — promotion flow live; bandit arms not recorded |
| **Key files** | `memory_promotion_service.py`, `memory_promotion_scorer.py`, `strategy_performance_ledger.py` |

### v4 promotion UCB lifecycle

| Stage | Bandit action | UCB role |
|-------|---------------|----------|
| Candidate queued | Arm = `memory:defer:{category}` | Explore low-confidence categories |
| Admin approves | Record win/loss after retrieval eval | Exploit high UCB promote arms |
| Admin rejects | Record loss on promote arm | Down-rank arm in category segment |
| Rollback | Record loss + revert arm stats | Prevent re-explore until cooldown |

### v4 acceptance criteria

- [ ] `record()` called on promotion approve/reject with memory strategy keys
- [ ] UCB ranks admin queue within category segment
- [ ] No auto-promote without human gate
- [ ] Admin summary exposes top memory arms + UCB scores

---

## v5 — Retrieval-source UCB

| Dimension | Detail |
|-----------|--------|
| **Purpose** | Learn which **RAG sources and rank modes** win for each org segment |
| **UCB variant** | UCB1 over source arms; optional weight blend with v5 `RetrievalRanker` scores |
| **Intel pairing** | Intelligence Engine **v5** — `RetrievalRanker`, `source_reliability_resolver` |
| **Arms** | `source:{connector_id}`, `rag:hybrid`, `rag:lexical`, `model:retrieval_ranker` |
| **Partial today** | `model:retrieval_ranker` already logged in v2 ledger — not full source-level UCB |
| **Outcome signal** | `rag_chunk_outcomes`, chunk helpfulness, response evaluation polarity |
| **Min data gate** | ≥ `100` labeled retrieval examples per org (matches v5 ranker gate) |
| **Runtime** | `UnifiedRetrievalService` rerank path chooses source mix from UCB + ranker |
| **Fallback** | Fixed reliability weights + lexical rerank (current v5 fallback) |
| **Storage** | `strategy_performance_records` with `strategy_family: retrieval` |
| **Services** | `UnifiedRetrievalService`, `source_reliability_resolver`, `StrategyPerformanceLedger` |
| **Admin surface** | Source reliability panel + UCB column per connector |
| **Status** | **PLANNED** — ranker + reliability live; source UCB selection not wired |
| **Key files** | `learning_to_rank.py`, `source_reliability_resolver.py`, `unified_retrieval_service.py` |

### v5 UCB + ranker blend (planned)

```
final_score(source) = α * ucb_score(source) + (1 - α) * ranker_weight(source)
```

`α` defaults to `0.5` until ranker TRAINED; then defers to ranker when artifact deployed.

### v5 acceptance criteria

- [ ] Per-connector win/loss recorded from chunk outcomes
- [ ] `choose_preferred_strategy` exposes retrieval arm family for RAG path
- [ ] UCB respects v5 min-example gate before overriding defaults
- [ ] Bandit status includes `source:*` arms in top_strategies

---

## v6 — Entity-graph contextual UCB

| Dimension | Detail |
|-----------|--------|
| **Purpose** | Bias route/enrichment arms using **entity context** (CRM-heavy vs glossary-heavy queries) |
| **UCB variant** | Segmented UCB1 on `entity:{primary_type}:{dept}:{task}` (LinUCB deferred — tabular first) |
| **Intel pairing** | Intelligence Engine **v6** — `org_entity_relationships`, `build_entity_context_section()` |
| **Arms** | `route:*:graph|no_graph:*`, enrichment toggles already in `build_route_strategy_key()` |
| **Entity resolution** | Primary entity type from one-hop `get_related_entities()` match on query |
| **Min data gate** | ≥ `10` decided samples per entity segment before UCB overrides default route |
| **Runtime** | `IntelligenceRouter` + `IntelligenceOrchestrator` prefer graph arms when entity UCB high |
| **Fallback** | v2/v3 segment UCB when entity type unknown |
| **GNN note** | `graph_neural_network` remains **PLANNED** — v6 bandit uses Postgres graph features only |
| **Storage** | `strategy_performance_records`; `metadata.entity_types` on rows |
| **Services** | `entity_relationship_service`, `intelligence_router.py`, `StrategyPerformanceLedger` |
| **Admin surface** | Relationships tab + entity-segment UCB breakdown |
| **Status** | **PLANNED** — graph prompt injection live; entity-segment bandit not wired |
| **Key files** | `entity_relationship_service.py`, `learning_strategy_keys.py`, `intelligence_router.py` |

### v6 entity segment examples

| Query signal | Primary entity | Example segment | Favored arm |
|--------------|----------------|-----------------|-------------|
| "status of Acme deal" | `deal` | `entity:deal:sales:question_answering` | `route:*:graph:*` |
| "what is churn?" | `glossary_term` | `entity:glossary_term:default:question_answering` | hybrid RAG + graph |
| No entity match | — | fallback v2 `dept:task` | default route |

### v6 acceptance criteria

- [ ] Entity primary type written to outcome `metadata` and segment key
- [ ] Graph vs no_graph arms accumulate separate win/loss stats
- [ ] UCB never enables graph enrichment without entity evidence
- [ ] Admin manifest lists v6 bandit as PLANNED until gates met

---

## Cross-version wiring matrix

| Consumer | v2 | v3 | v4 | v5 | v6 |
|----------|----|----|----|----|-----|
| `ModelSelector` | ✅ LLM + ML UCB | cluster segment (planned) | — | — | — |
| `IntelligenceRouter` | ✅ route keys recorded | cluster segment (planned) | — | retrieval arms (planned) | graph arms (planned) |
| `UnifiedRetrievalService` | ranker key in ledger | — | — | ✅ source UCB (planned) | glossary entity boost |
| `memory_promotion_service` | — | — | ✅ promotion UCB (planned) | — | — |
| `IntelligenceOutcomeCoordinator` | ✅ record + segment | cluster segment (planned) | memory arms (planned) | source arms (planned) | entity metadata (planned) |
| Admin bandit UI | ✅ W/L/rate/UCB | cluster column (planned) | memory tab (planned) | source column (planned) | entity segment (planned) |
| `long_horizon_policy_service` | ✅ `tabular_ledger_v2` | manifest slot (planned) | manifest slot (planned) | manifest slot (planned) | manifest slot (planned) |

---

## Policy escalation ladder (how versions compose)

```
v6 entity segment UCB
  ↓ fallback if under-gated
v3 cluster segment UCB
  ↓ fallback if under-gated
v2 org-wide UCB1 + win-rate
  ↓ fallback if under-gated
ModelRouter / catalog defaults
```

v4 and v5 operate on **orthogonal arm families** (memory promotion queue, RAG source mix) and do not replace the route/LLM ladder — they merge at their respective services.

---

## Admin & manifest API (current + planned)

| Endpoint | v2 today | v3–v6 planned fields |
|----------|----------|----------------------|
| `GET .../learning/bandit-status` | `top_strategies[].ucb_score`, `bandit_version: v2` | `segments[]`, `cluster_id`, `entity_type`, `source_id` |
| `GET .../learning/live-dashboard` | `bandit.summary` + Phase E manifest | `bandit.versions.v3–v6.status` per component |
| `GET .../learning-progress` | Model readiness | Bandit version readiness gates |

Honest gate response (applies to each planned version):

```json
{
  "bandit_version": "v3",
  "status": "planned",
  "reason": "insufficient_segment_samples",
  "required_per_arm": 5,
  "active_policy": "v2"
}
```

---

## Acceptance criteria (bandit ladder complete)

- [x] v2 UCB1 live — win-rate exploit + UCB explore + segment weights
- [x] v3 cluster-segment UCB live with v2 fallback
- [x] Admin UI shows UCB column (`BanditStatusCard`)
- [x] `active_bandit_version: v3` in policy manifest
- [ ] v4 memory-promotion arms with human gate preserved
- [ ] v5 source-level UCB integrated with retrieval ranker
- [ ] v6 entity-segment UCB for graph route arms
- [ ] No v3–v6 version reported as LIVE without min-sample gates passing
- [ ] Neural RL remains gated — tabular UCB stays default even after v6

---

## References

- Phase E v2 (live): [`PHASE_E_LONG_HORIZON_SPEC.md`](PHASE_E_LONG_HORIZON_SPEC.md)
- Intelligence Engine v3–v6: [`INTELLIGENCE_ENGINE_V3_V6_TABLES.md`](INTELLIGENCE_ENGINE_V3_V6_TABLES.md)
- Ledger implementation: `backend/app/services/strategy_performance_ledger.py`
- Strategy keys: `backend/app/services/learning_strategy_keys.py`
- Model selection: `backend/app/services/model_selector.py`
- Policy manifest: `backend/app/services/long_horizon_policy_service.py`
- Architecture registry: `backend/app/ai_architecture_registry.py` (`tabular_bandit_v2`)
