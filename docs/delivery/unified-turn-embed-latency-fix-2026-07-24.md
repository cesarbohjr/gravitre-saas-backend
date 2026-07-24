# Unified turn embedding retrieval latency fix (2026-07-24)

## Phase 0 — Root cause (pre-fix, prod `22b58658…`, 70 tools)

`narrow_tools_ms` ≈ `pre_model_ms` (1048ms) with **no sub-breakdown** in audit. Code review + local instrumentation identified:

| Component | Pre-fix behavior | Expected cost |
|-----------|------------------|---------------|
| Query embed | `get_embedding()` → `OpenAIAdapter.embed()` → **new `OpenAI()` client per call** | ~300–500ms RTT + TCP/TLS |
| Tool-doc embed | `_embed_tools()` loop: **sequential `get_embedding()` per cache-missed candidate** | N × RTT (not using warm cache batch) |
| Query + tool docs | **Sequential** (query first, then tool loop) | Sum of both |
| Boot warm | `asyncio.create_task(_warm_unified_tool_embeds())` — **fire-and-forget** | First requests race warm; cache cold |
| Vector rank | In-process `_cosine()` | ~0ms (not bottleneck) |

Warm cache existed (`_TOOL_EMBED_CACHE`) but per-request path still paid full RTT when misses occurred; primary bug was **connection churn + N sequential API calls**, not missing cache structure.

## Phase 1 — Fix shipped

1. **Shared sync OpenAI client** (`backend/app/rag/embedding.py` `_get_sync_openai_client`) — connection reuse for all embedding calls; `OpenAIAdapter.embed()` delegates to same client.
2. **Batch tool-doc embeddings** — `embed_texts_batch_openai()` single `embeddings.create(input=[...])` for cache misses.
3. **Parallel query + tool-doc work** — `ThreadPoolExecutor` overlaps query embed with cache lookup + batch embed.
4. **Await boot warm** — `main.py` lifespan `await _warm_unified_tool_embeds()` before accepting traffic.
5. **Phase 0 instrumentation** — `latency_breakdown` keys: `embed_query_ms`, `embed_tool_docs_ms`, `embed_tool_doc_cache_hits/misses`, `embed_tool_doc_batch_api_calls`, `embed_similarity_rank_ms`, `embed_narrow_total_ms`.

## Phase 2 — Post-fix A/B (pending live run)

Re-run at 70 tools, `email_intent`, embedding gate temporarily at 40:

| Path | `narrow_tools_ms` | `embed_query_ms` | `embed_tool_docs_ms` | cache hits | `model_ttft_ms` | wall |
|------|------------------:|-----------------:|---------------------:|-----------:|----------------:|-----:|
| Embedding (pre-fix) | 1048 | — | — | — | 1024 | 2073 |
| Keyword (baseline) | 1 | — | — | — | 802 | 804 |
| **Embedding (post-fix)** | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |

Artifact: `docs/delivery/unified-turn-task-ttft-70tools-embedding-post-fix-turn1.json`

## Phase 3 — Threshold decision (pending Phase 2)

Stopgap `UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=200` remains until post-fix A/B shows evidence-based crossover.
