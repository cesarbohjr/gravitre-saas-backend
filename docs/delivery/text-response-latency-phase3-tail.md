# Text-response latency — Phase 3 tail investigation

**Status:** DONE on tip `5e068eb1`  
**Tip at diagnosis:** `8c21d5c1`  
**Artifacts:** `phase3-ttft-tail-audit.json`, `phase3-ttft-tail-worst-detail.json`, `unified-turn-task-ttft-phase3-post-tail-fix.json`

## Prod distribution (7d, n=224 with TTFT)

| Metric | ms |
|--------|-----|
| wall p50 | 806 |
| wall p90 | 1810 |
| wall p95 | 2157 |
| wall p99 | 2846 |
| wall **max** | **20904** |

Tail (slowest 10%, n=22) cause tags: cold_cache 11, fallthrough 9, slow_narrow/embed/pre_model 6 each, slow_model_ttft≥3s 2.

## Extreme outlier root cause (confirmed)

`2026-08-05T20:15:37Z` hubspot_search / `read_tool_classical`:

| Field | Value |
|-------|-------|
| wall_to_first_token_ms | **20904** |
| model_ttft_ms (round 2) | 4894 |
| pre_first_token_overhead_ms | **16010** |
| progressiveSearchRounds | **1** |
| progressive_loaded | hubspot_search_contacts |
| topSimilarity | 0.7489 |
| narrow_tools_ms | 88 |

**Mechanism:** progressive disclosure attached stubs only → model spent ~16s on round-1 `search_catalog_tools` → round-2 real tool call (~4.9s). Wall TTFT is measured from shadow start through round-2 first delta, so the search round dominates the max.

Secondary: cold MiniLM encode (~800ms+) on some workers; stream rounds had no hard timeout.

## Fix

1. Preload top-2 narrowed connector tools with full schemas when similarity ≥ 0.2 (or keyword path).
2. `asyncio.wait_for` per stream round (`unified_turn_stream_timeout_s`, default 20s).
3. Record `progressive_round_ms` / `progressive_preloaded` / `stream_timed_out`.
4. Warm local MiniLM encoder at boot alongside tool-doc cache.

## Post-deploy verification (tip `5e068eb1`)

| Battery | wall p50 | wall max | notes |
|---------|---------:|---------:|-------|
| phase3-post-tail-fix (`ef7ef50f`) | 735 | 2599 | preload briefly targeted browser_* — fixed in `5e068eb1` |
| phase4-standing-gate (`5e068eb1`) | **973** | **1840** | HubSpot preload = hubspot_*; no search-round overhead |

Max class **20904 → 1840**. Gate honesty is Phase 4.
