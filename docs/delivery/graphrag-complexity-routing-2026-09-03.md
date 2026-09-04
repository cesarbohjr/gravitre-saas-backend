# GraphRAG + complexity routing delivery (2026-09-03)

## Part 1 — Graph relationship traversal

### Phase 0 audit
- Org graph: `org_entity_relationships` + `org_knowledge_nodes` (One Brain).
- Hot path before this change: `unified_retrieval_service` → `answer_business_question` → **one-hop only**.
- `traverse_multi_hop()` existed but was not selected for relationship-shaped queries.

### Phase 1 shipped
- `graph_query_intent.py`: relationship detection, name resolution via `org_knowledge_nodes`, topic path ranking.
- `knowledge_graph_service.answer_business_question`: multi-hop when query shape is relationship; one-hop otherwise.
- `task_classifier`: `relationship_lookup` intent sets `requires_graph`.
- Graph results still append to unified retrieval `sources` as `kind: graph` (same ranking layer).

### Live scenario
- Query: "How is Acme related to our Q3 pipeline decline?"
- Unit proof: `test_acme_relationship_query_uses_multi_hop` walks company → deal → kpi paths.

## Part 2 — General complexity routing

### Phase 0 audit
- Voice: `reasoning_depth` in `agent_intelligence.py` (conversational vs full).
- General: `classify_routing_tier()` applied all surfaces but without legal/financial floor.
- COGS basis: `MODEL_TIERS` + `_MODEL_PRICING_PER_1K` in `model_router.py`.

### Phase 1 shipped
- `complexity_routing_guardrails.py`: high-risk message + classification floor, mandatory critic extension, COGS estimator.
- `classify_routing_tier`: message-time high-risk floor; pinned-fast bypass for high-risk.
- `agent_intelligence`: post-classification escalate-only floor; `requires_mandatory_critic()` for legal/financial.

### Mutation proof
- `test_mutation_misclassified_high_risk_caught` — simple + high_risk → research.

### COGS (honest, synthesis-only estimate)
- Simple extraction ("What is Gravitre?"): routes `simple` / low tier vs prior default `multi_step`.
- See `estimate_cogs_delta_simple_vs_prior()` — reports before/after USD with token assumptions documented in test output.

## Verification status
- Local pytest: run `pytest backend/tests/services/test_graph_* backend/tests/services/test_complexity_*`
- Production: pending deploy + `/health` git_sha + live Acme trace after push.
