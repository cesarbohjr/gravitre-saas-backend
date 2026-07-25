# Unified turn query-embed local fix — FINAL (2026-07-25)

**Shipped:** `7afecfb9` (code) · **Verified:** prod `81ff4a26…` @ embed_min=40

## Phase 5 — Query-embed diagnosis (confirmed)

The ~427ms was **100% remote OpenAI API round-trip** for a single query vector. Tool-doc side was already cache-fixed (0ms, full hits). Sub-breakdown on prod before local fix:

| Field | ms |
|---|---:|
| `embed_query_ms` | 427 |
| `embed_query_encode_ms` | (not split — all network) |
| `embed_tool_docs_ms` | 0 |

## Phase 5 fix — Local SentenceTransformer

`backend/app/rag/tool_retrieval_embedding.py`: `all-MiniLM-L6-v2` in-process for query + tool-doc vectors; normalized query cache (TTL 300s).

**PASS — live breakdown** `unified_turn.live.completed` @ 2026-07-25T05:07:55Z (`74251fcb…`, `email_intent`):

| Field | Remote (9496cedf) | **Local (81ff4a26)** |
|---|---:|---:|
| `embed_query_ms` | 427 | **19** |
| `embed_query_encode_ms` | — | **19** |
| `embed_query_method` | openai | **local** |
| `narrow_tools_ms` | 434 | **24** |
| `pre_model_ms` | 435 | **32** |

Query cache hit on repeat phrasing: `embed_query_provider=local_cache`, sub-ms lookup (see unit tests).

## Phase 6 — Final A/B (`email_intent`, 70 tools)

Artifact: [`unified-turn-task-ttft-70tools-embedding-local-turn1.json`](unified-turn-task-ttft-70tools-embedding-local-turn1.json)

| Path | `narrow_tools_ms` | `embed_query_ms` | `model_ttft_ms` | **wall** | payload B |
|------|------------------:|-----------------:|----------------:|---------:|----------:|
| Keyword (9496cedf) | 1 | — | 837 | **840** | 12355 |
| Embedding remote (9496cedf) | 434 | 427 | 830 | 1269 | 4706 |
| **Embedding local (81ff4a26)** | **24** | **19** | **454** | **487** | 4701 |

**Embedding wins end-to-end** at 70 tools with local query embed.

### Threshold decision (FINAL)

`UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS` **200 → 40** (config default). The 200 stopgap applied only while query embed was a remote 427ms RTT; local in-process embed removes that blocker. Crossover at 26 tools not re-run in this session; 70-tool win is definitive for current prod catalog.

### Same-conversation cache (embedding + local)

From same artifact — `email_intent` turn-2: `model_ttft_ms` 454 → 522 (+68ms, prefix cache ratio 93.1% → 94.5%). Cache path still healthy.

## Phase 7 — Infrastructure sweep

| Site | Fix | Status |
|------|-----|--------|
| `knowledge_intelligence_service._embed_queries` | Sequential → batch | **Shipped** |
| `resolve_query_cluster_for_bandit` | Per-row → batched reps | **Shipped** |
| `intelligence_training.py` | Sequential → batch when len>1 | **Shipped** |
| `embedding.py` shared client | Prior commit | ✓ |
| `rag/ingest.py` per-chunk embed loop | Offline ingest | Documented follow-up |
