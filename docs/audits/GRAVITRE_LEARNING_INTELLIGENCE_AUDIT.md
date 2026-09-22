# GRAVITRE — LEARNING AND INTELLIGENCE AUDIT

**Audit only.** Marketing words vs technical reality.

---

## Classification of “ML / intelligence” components

| Name in product | Actual mechanism | Value vs LLM/rules | Disposition |
|-----------------|------------------|--------------------|-------------|
| Unified LIVE / ReAct | LLM tool calling | Core | PRESERVE + CONVERGE |
| Intent Gateway | heuristics + optional LLM | latency | OPTIMIZE |
| Tool embedding JIT | local MiniLM similarity | reduces tokens | PRESERVE |
| RAG embeddings | OpenAI t-e-3-small + pgvector | retrieval | OPTIMIZE consumption |
| Reranker | cross-encoder MiniLM | ranking | PRESERVE until eval |
| Entity fabric | HMAC exact mention | safety | PRESERVE |
| Knowledge graph UI | stored relations + viz | display | PRESERVE UI; not a brain |
| Outcome learning | event table + later prompts | **weak closed loop** | OPTIMIZE |
| Predictive / reports | aggregation + LLM narrative | mixed | do not brand as trained |
| Fine-tune gpt-4.1-mini | training **path** in code | **UNKNOWN** if serving | investigate |
| Composer | LLM rewrite | latency tax | OPTIMIZE |
| QA critic | LLM | prod hooks true | keep on high risk |

There is **no** documented production sklearn/xgboost churn model with versioning, drift monitors, and rollback serving the chat kernel. If one exists off the cognitive path, it is **UNKNOWN** to this audit.

---

## Learning loop (objective → later behavior)

```
business objective
  → decision / plan
  → action (ActionSpec)
  → observation (provider)
  → intelligence_outcome_events  (persist: YES, CODE/prior)
  → model/state update           (WEAK — not a trained weights refresh)
  → later planning consumes      (PARTIAL / UNRELIABLE)
```

Questions:

| Question | Answer | Evidence |
|----------|--------|----------|
| What changes after an outcome? | Event row; prompt snippets if wired | CODE INSPECTED |
| Persisted? | yes, tenant-scoped table | CODE |
| Later behavior consume? | not guaranteed on every LIVE turn | CODE |
| Correctable / expirable? | UNKNOWN completeness | UNKNOWN |
| Contradictory override? | UNKNOWN | UNKNOWN |
| Bad outcome poison? | **risk** if API 200 labeled win | INFERRED |
| Tenant isolated? | intended | CODE |
| Explainable? | event fields; not a model card | CODE |
| API success = business success? | **must not**; currently a known confusion | CODE INSPECTED / program notes |

**Does Gravitre genuinely learn?** It **records** and sometimes **retrieves**. It does **not** (on evidence here) run a supervised business-outcome model that changes tool policy with validation. **OUTCOME LEARNING: WEAK.**

---

## Knowledge Fabric vs execution

- Documents/chunks/embeddings exist.  
- Chat may retrieve.  
- Tool turns often skip fabric and hit connectors.  
- Graph is more **UI Intelligence** than planner input.  
- Freshness/provenance/confidence: **PARTIAL** in schema, **UNKNOWN** in live CEO questions (OAuth blocked).  
- Fabric driving execution: **NO as default**; **YES as optional retrieval**.

---

## Intelligence UI vs engine

The Intelligence page must remain a **window**. Backend cognition is Kernel + LIVE/ReAct + stores. If UI concepts (layers, “org brain”) leak into new services, cohesion drops. **PRESERVE UI; do not grow a parallel API.**

---

## Memory efficiency

- durable_checkpoint: **LIVE proven** (conv `c2e362ec-…` after persist+normalize fix).  
- Full history still compiled many turns: **CODE INSPECTED**.  
- Compaction / working memory: **PARTIAL**.  
- Long Manus-style jobs cannot rely on replay alone — checkpoint is the preserve path; **EXTEND** consumption, don’t add a new memory product.

---

## ML model inventory (actual)

| Model | Type | Train pipeline | Serving | Preserve? |
|-------|------|----------------|---------|-----------|
| t-e-3-small | embedding API | vendor | RAG | PRESERVE |
| MiniLM tool embed | local embed | vendor weights | JIT | PRESERVE |
| MiniLM rerank | cross-encoder | vendor | RAG | OPTIMIZE/eval |
| OpenAI/Anthropic/Gemini chat | LLM | vendor | kernel | OPTIMIZE routing |
| Fine-tunes | UNKNOWN artifacts | path in repo | UNKNOWN | do not claim trained |

Refresh frequency, drift detection, rollback of **Gravitre-owned** weights: **ABSENT / UNKNOWN**.
