# Intelligence Engine v3–v6 — Version Tables (binding)

Status: **Live** (all four layers shipped and wired).  
Last updated: 2026-07-03.

These tables document the **foundational intelligence stack** (v3→v6) that predates Phase E long-horizon learning. v7+ (response evaluation, outcome attribution, tabular bandit v2) extend this stack — see [`PHASE_E_LONG_HORIZON_SPEC.md`](PHASE_E_LONG_HORIZON_SPEC.md).

---

## Version ladder (summary)

| Version | Name | Primary question | Catalog model | Status |
|---------|------|------------------|---------------|--------|
| **v3** | Query intelligence | What is the org asking about? Where are knowledge gaps? | `query_clusterer` | **LIVE** |
| **v4** | Memory promotion | Which memories should be promoted or suppressed? | `memory_promotion_scorer` | **LIVE** |
| **v5** | Retrieval learning | Which sources rank best for this org? | `retrieval_ranker` | **LIVE** |
| **v6** | Entity graph | What business entities relate to this query? | (graph traversal, not ML) | **LIVE** |

Training entrypoint: `train_retrieval_memory_learner()` runs v3 + v4 + v5 in one pass (`intelligence_training.py`).

---

## v3 — Query clustering & knowledge gaps

| Dimension | Detail |
|-----------|--------|
| **Purpose** | Cluster org queries, extract glossary terms, surface open knowledge gaps for admin action |
| **Train function** | `train_v3_query_clusterer()` |
| **ML model** | `QueryClusterer` (HDBSCAN-style embedding clusters) |
| **Catalog status** | `TRAINED` when ≥40 distinct normalized queries (90-day corpus) |
| **Min data gate** | 40 distinct queries (`MIN_CLUSTERING_ROWS`) |
| **Persisted tables** | `org_query_clusters`, `org_glossary_terms`, `org_knowledge_gaps` |
| **Services** | `knowledge_intelligence_service.run_query_clustering`, `identify_knowledge_gaps`, `run_glossary_extraction` |
| **Orchestration** | `company_intelligence_orchestrator` — cluster + gap pass on company intel refresh |
| **Graph link** | `entity_relationship_builder.build_relationships_from_query_clusters` → v6 edges |
| **Runtime in chat** | Indirect — gaps inform company intelligence snapshot; cluster labels in admin dashboard |
| **Admin API** | `GET /api/admin/intelligence` snapshot includes query cluster sections |
| **Agent prompt** | Referenced in operator system prompt as “v3 knowledge gaps” |
| **Fallback** | Rule-based gap heuristics when clusters sparse; no fake cluster counts |
| **Key files** | `backend/app/ml/intelligence_training.py`, `backend/app/services/knowledge_intelligence_service.py`, `backend/app/ml/clustering.py` |

### v3 data flow

```
assistant_queries / message corpus
  → normalize + embed
  → QueryClusterer.train
  → org_query_clusters + glossary
  → identify_knowledge_gaps (open rows)
  → entity_relationship_builder (v6)
```

---

## v4 — Memory promotion scoring

| Dimension | Detail |
|-----------|--------|
| **Purpose** | Prioritize memory promotion candidates (approve/reject) from observed usage patterns |
| **Train function** | `train_v4_memory_promotion_scorer()` |
| **ML model** | `MemoryPromotionScorer` (classifier on candidate features) |
| **Catalog status** | `TRAINED` when ≥15 resolved promotion candidates |
| **Min data gate** | 15 resolved candidates (`MemoryPromotionScorer.MIN_TRAINING_EXAMPLES`) |
| **Source table** | `memory_promotion_candidates` (status, frequency, department_count, category) |
| **Services** | `memory_promotion_service` (approve/reject/rollback flows) |
| **Orchestration** | Company intelligence refresh trains v4 after cluster pass |
| **Runtime in chat** | Promoted memories enter `agent_memories` / hybrid retrieval; scorer ranks admin queue |
| **Admin API** | `GET/POST /api/admin/memory-promotion/*` |
| **Admin UI** | Admin → Intelligence → Memory Promotion tab |
| **Fallback** | Rule-based promotion thresholds when model not trained |
| **Key files** | `backend/app/ml/memory_promotion_scorer.py`, `backend/app/services/memory_promotion_service.py`, `backend/app/routers/memory_promotion.py` |

### v4 promotion lifecycle

| Stage | Storage | Human gate |
|-------|---------|------------|
| Candidate detected | `memory_promotion_candidates` | Auto |
| Scorer ranks queue | ML artifact in model registry | Admin review |
| Approved | `agent_memories` + provenance | Required |
| Rejected / rolled back | Status + audit | Required |

---

## v5 — Retrieval ranker (learned source reliability)

| Dimension | Detail |
|-----------|--------|
| **Purpose** | Learn per-org source reliability weights from evaluated retrieval outcomes |
| **Train function** | `train_v5_retrieval_ranker()` |
| **ML model** | `RetrievalRanker` (`learning_to_rank.py`) |
| **Catalog status** | `TRAINED` when ≥100 labeled retrieval examples |
| **Min data gate** | 100 examples (`RetrievalRanker.MIN_TRAINING_EXAMPLES`) |
| **Training signal** | `rag_chunk_outcomes`, response evaluations, helpfulness labels |
| **Unified interface** | `RetrievalMemoryLearner` wraps v3/v4/v5/v7 (`retrieval_learning.py`) |
| **Runtime** | `source_reliability_resolver` + hybrid RAG rerank path when model deployed |
| **Orchestration** | `UnifiedRetrievalService` → `RAGService.retrieve_hybrid_rows` |
| **Strategy key** | `model:retrieval_ranker` in `strategy_performance_records` (Phase E bandit) |
| **Fallback** | Fixed reliability weight + lexical rerank |
| **Key files** | `backend/app/ml/learning_to_rank.py`, `backend/app/services/source_reliability_resolver.py`, `backend/app/ml/retrieval_learning.py` |

### v5 vs v7 note

| Layer | Role |
|-------|------|
| **v5** | Learned ranker weights from org-specific retrieval feedback |
| **v7** | `response_evaluation_service` + `retrieval_memory_learner` — evaluation envelope and unified export |
| **Runtime** | Both feed `RetrievalMemoryLearner`; v5 artifact is the deployable ranker |

---

## v6 — Entity graph context

| Dimension | Detail |
|-----------|--------|
| **Purpose** | One-hop business entity relationships injected into agent/assistant prompts |
| **Train function** | None (deterministic graph build, not ML) |
| **Graph builder** | `rebuild_org_entity_relationships()` in `entity_relationship_builder.py` |
| **Storage** | `org_entity_relationships` |
| **Entity types** | `deal`, `contact`, `company`, `workflow`, `agent`, `glossary_term`, `query_cluster`, `department`, … |
| **Traversal** | `get_related_entities()` — one hop, confidence + evidence_count sort |
| **Prompt injection** | `build_entity_context_section()` → `<entity_graph>` block |
| **Orchestration** | `IntelligenceOrchestrator`, `AgentIntelligence.execute_task` |
| **Architecture registry** | `enterprise_knowledge_graph` — live, backed by v6 |
| **GNN model** | `graph_neural_network` — **PLANNED** (Postgres traversal is v6 substitute) |
| **Admin API** | `GET /api/admin/intelligence/entity-relationships` |
| **Admin UI** | Admin → Intelligence → Relationships tab |
| **Fallback** | Empty entity block when no matching glossary/CRM entities in query |
| **Key files** | `backend/app/services/entity_relationship_service.py`, `backend/app/services/entity_relationship_builder.py`, `backend/app/services/knowledge_graph_service.py` |

### v6 relationship sources

| Source system | Edge types built from |
|---------------|----------------------|
| CRM connectors | Deals, contacts, companies |
| Workflows | Run → agent, step outputs |
| v3 clusters | Query cluster ↔ glossary |
| Glossary | Term co-occurrence in queries |
| Agents | Department / handoff links |

---

## Cross-version wiring matrix

| Consumer | v3 | v4 | v5 | v6 |
|----------|----|----|----|----|
| `company_intelligence_orchestrator` | ✅ train + gaps | ✅ train | ✅ train | ✅ rebuild graph |
| `IntelligenceOrchestrator` | via company snapshot | via memories | via unified retrieval | ✅ entity block |
| `AgentIntelligence` / ReAct | indirect | promoted memories | RAG rank | ✅ entity block |
| `UnifiedRetrievalService` | cluster context (hybrid) | agent memories | ✅ ranker weight | glossary match |
| Admin Intelligence UI | clusters + gaps | promotion tab | model readiness | relationships tab |
| Phase E bandit ledger | — | — | ✅ strategy keys | — |

---

## Training & readiness API

| Endpoint | Returns |
|----------|---------|
| `GET /api/admin/intelligence/learning-progress` | Per-model readiness including v3/v4/v5 |
| `GET /api/admin/learning/status` | Learning layer registry status |
| `POST /api/admin/intelligence/train` (if exposed) | Component train results with `insufficient_data` gates |

Honest gate response shape:

```json
{
  "trained": false,
  "reason": "insufficient_data",
  "required": 40,
  "distinct_queries": 12
}
```

---

## Acceptance criteria (v3–v6 complete)

- [x] v3 clusters + gaps persist to org tables and appear in admin snapshot
- [x] v4 scorer trains only above min resolved candidates; admin promotion flow live
- [x] v5 ranker trains only above 100 examples; feeds retrieval when deployed
- [x] v6 relationships rebuild from CRM + clusters + glossary; prompt injection live
- [x] Unified training pass (`train_retrieval_memory_learner`) orchestrates v3+v4+v5
- [x] No PLANNED model presented as TRAINED without registry artifact

---

## References

- Training: `backend/app/ml/intelligence_training.py`
- Company intel refresh: `backend/app/services/company_intelligence_orchestrator.py`
- Phase E (v7/v8 + bandit v2): [`PHASE_E_LONG_HORIZON_SPEC.md`](PHASE_E_LONG_HORIZON_SPEC.md)
- Bandit v3–v6 UCB ladder: [`BANDIT_V3_V6_TABLES.md`](BANDIT_V3_V6_TABLES.md)
- Universal layer waves 4–9: [`UNIVERSAL_INTELLIGENCE_LAYER_SPEC.md`](UNIVERSAL_INTELLIGENCE_LAYER_SPEC.md) (Intelligence waves section)
- ML catalog: `backend/app/ml/model_catalog.py`
