# Unified turn query-embed local fix + infrastructure sweep (2026-07-24)

## Phase 5 — Query-embed diagnosis (pre-local)

Prod warm-cache run (`9496cedf`, `email_intent`):

| Sub-component | ms | Root cause |
|---|---:|---|
| `embed_query_ms` | **427** | Remote OpenAI API round-trip (not TLS churn; shared client confirmed) |
| `embed_tool_docs_ms` | 0 | Boot-warmed cache (49/49 hits) |
| `embed_similarity_rank_ms` | 5 | In-process cosine |

## Phase 5 fix

Local `all-MiniLM-L6-v2` via `sentence-transformers` (already in prod deps for cross-encoder rerank) for **both** query and tool-doc vectors in unified-turn retrieval only. Query normalized-text cache (TTL 300s).

New module: `backend/app/rag/tool_retrieval_embedding.py`

## Phase 6 — Final A/B

See `unified-turn-task-ttft-70tools-embedding-local-turn1.json` (post-deploy).

## Phase 7 — Infrastructure sweep

| Site | Fix |
|------|-----|
| `knowledge_intelligence_service._embed_queries` | Sequential → `embed_texts_batch_openai` |
| `resolve_query_cluster_for_bandit` | Per-row embed → batched rep texts |
| `intelligence_training.py` | Sequential loop → batch when len>1 |
| `rag/ingest.py` chunk loop | Documented follow-up (offline ingest) |
