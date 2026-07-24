# Unified turn embedding retrieval latency fix (2026-07-24)

**Shipped:** `9496cedf` · prod verified 2026-07-24T20:17Z

## Phase 0 — Root cause breakdown

Pre-fix prod (`22b58658…`, 70 tools, `email_intent`): `narrow_tools_ms=1048` ≈ `pre_model_ms` with no sub-breakdown.

Code review identified:

| Component | Pre-fix behavior | Post-fix (prod `9496cedf`, warm cache) |
|-----------|------------------|----------------------------------------|
| Query embed | New `OpenAI()` client per call via `OpenAIAdapter.embed()` | Shared sync client; **`embed_query_ms=427`** |
| Tool-doc embed | Sequential `get_embedding()` per cache-missed candidate | Batch `embeddings.create(input=[…])`; boot warm awaited |
| Query + tool docs | Sequential | Parallel (`ThreadPoolExecutor`) |
| Boot warm | Fire-and-forget `create_task` | `await _warm_unified_tool_embeds()` in lifespan |
| Vector rank | In-process `_cosine()` | **`embed_similarity_rank_ms=5`** (unchanged, not bottleneck) |
| Tool-doc cache | Structure existed but cold path paid N× RTT | **`embed_tool_doc_cache_hits=49`, misses=0, embed_tool_docs_ms=0`** |

**PASS — Phase 0 live breakdown:** `unified_turn.live.completed` @ 2026-07-24T20:17:43Z (`95a277e2…`, `email_intent`).

## Phase 1 — Fix

1. Process-wide sync OpenAI client (`backend/app/rag/embedding.py`).
2. Batch tool-doc embeddings for cache misses.
3. Parallel query embed + tool-doc load.
4. Await boot-time cache warm (`backend/app/main.py`).
5. Sub-timings in `latency_breakdown` (`embed_query_ms`, `embed_tool_docs_ms`, cache hit/miss counts, etc.).

## Phase 2 — Post-fix A/B (70 tools, `email_intent`, turn-1)

Same tip `9496cedf`, gate temporarily `40` for measurement only.

| Path | Artifact | `narrow_tools_ms` | `embed_query_ms` | cache hits | `model_ttft_ms` | wall | payload B |
|------|----------|------------------:|-----------------:|-----------:|----------------:|-----:|----------:|
| Embedding pre-fix | `57tools-embedding-turn1.json` | 1048 | — | — | 1024 | 2073 | 4706 |
| **Embedding post-fix** | `70tools-embedding-post-fix-turn1.json` | **434** | **427** | 49/49 | **830** | 1269 | 4706 |
| Keyword (same tip) | `70tools-keyword-post-fix-turn1.json` | 1 | — | — | **837** | **840** | 12355 |

- **Fix impact:** `narrow_tools_ms` **−59%** (1048→434). Tool-doc side eliminated on warm cache (0ms, full hits).
- **Remaining cost:** query embed alone ~427ms — now the sole pre-model bottleneck.
- **End-to-end:** keyword still wins wall time (840 vs 1269) despite post-fix embedding having *slightly* lower `model_ttft_ms` (830 vs 837) from smaller payload.

## Phase 3 — Threshold decision

**Keep `UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=200`.** Post-fix embedding is materially faster but **does not beat keyword end-to-end at 70 tools**. No evidence-based crossover found at 26, 40, 55, or 70. Phase 4 enhancements **not pursued** (embedding path not competitive enough to justify added complexity).

Railway gate restored to **200** after A/B (`apply-railway-unified-turn-embed-gate.ps1`).

## Same-conversation cache (embedding path post-fix)

Artifact: `70tools-embedding-post-fix-cache.json`

| Probe | Turn 1 `model_ttft_ms` | Turn 2 | Δ |
|-------|------------------------|--------|---|
| email_intent | 1651 | 660 | **−991** |
| deals_status | 711 | 1665 | +954 |

Prefix caching works on embedding path (email_intent −991ms turn-2). deals_status turn-2 noisy (+954ms) — same pattern as keyword baseline variance.

## Phase 4

Not shipped — gated on Phase 2/3 showing embedding viability; criterion not met at current scale.
