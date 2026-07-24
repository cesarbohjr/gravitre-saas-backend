# Unified turn TTFT — 70-tool catalog retrieval A/B (2026-07-24)

**Prod tip:** `22b58658…` · `total_tools=70` (catalog crossed embed gate; was 26 at 436ms baseline)

## Invalid comparison (confirmed)

| Baseline artifact | Catalog | Retrieval | email_intent `model_ttft_ms` |
|-------------------|---------|-----------|------------------------------|
| `unified-turn-task-ttft-after-embed-gate-or-low-tier.json` | **26** | **keyword** (`embed_min=40` gated off) | **436** |
| Recent runs vs that baseline | **57–70** | **embedding** (catalog ≥ 40) | **666–1024+** |

The 436ms / 571ms comparison mixes **catalog size**, **retrieval method**, and **prompt-cache state**. Not one variable.

## 1 — email_intent ~900ms `pre_model_ms`: embedding path at gate threshold

**PASS — confirmed from audit `latency_breakdown`.**

| Run | `total_tools` | `retrieval_method` | `narrow_tools_ms` | `pre_model_ms` | `model_ttft_ms` |
|-----|---------------|--------------------|--------------------:|---------------:|----------------:|
| `unified-turn-task-ttft-baseline.json` (2026-07-23) | 57 | `embedding_narrow_tools_for_turn` | **907** | **908** | 909 |
| `57tools-embedding-turn1.json` (cold embed) | 70 | embedding | **1048** | **1049** | 1024 |
| `57tools-embedding-turn1.json` (warm fallthrough probes) | 70 | embedding | 250–442 | 250–444 | 594–1616 |
| `same-conversation-cache.json` (warm) | 57 | embedding | **492** | **493** | 1459 |

`narrow_tools_ms` ≈ `pre_model_ms` → overhead is **query-embed + tool-doc embed RTT** inside `embed_narrow_tools_for_turn`, not registry or prompt assembly. First turn after cache cold ≈ **900–1050ms**; warm ≈ **250–500ms** (still non-trivial).

Gate documentation (`config.py`, `unified-turn-task-latency-cd-status.md`) explicitly says **40 is not empirically validated** and must be revisited when catalog crosses threshold — **this is that data**.

## 2 — Apples-to-apples A/B (same tip, same catalog, one variable)

**Method:** Railway `UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS=999` forces keyword at 70 tools; default `40` enables embedding. Turn-1 only (`TTFT_SKIP_FOLLOW_UP=1`). Primary probe: **`email_intent`** (consistent `unified_turn.live.completed`).

| Path | Artifact | `retrieval_method` | `narrow_tools_ms` | `tools_payload_b` | `visible_tools` | **`model_ttft_ms`** | wall |
|------|----------|--------------------|------------------:|------------------:|------------------:|--------------------:|-----:|
| **Embedding** | `unified-turn-task-ttft-57tools-embedding-turn1.json` | `embedding_narrow_tools_for_turn` | 1048 | 4706 | 16 | **1024** | 2073 |
| **Keyword** | `unified-turn-task-ttft-70tools-keyword-turn1.json` | `keyword_narrow_tools_for_turn` | 1 | 12355 | 35 | **802** | 804 |

**Keyword wins at 70 tools** despite **2.6× larger tool payload** (12355 vs 4706 B). Embedding saves schema bytes but adds **~1s pre-model RTT** that dominates `model_ttft`.

Unified-live `model_ttft_p50` over all probes with live audit (embedding run): skewed by fallthrough — use **email_intent** as the clean comparator.

## 3 — Gate threshold / implementation assessment

| Finding | Implication |
|---------|-------------|
| At 70 tools, embed adds ~1048ms `narrow_tools_ms` | Fixed RTT per turn (query embed + candidate doc embeds) |
| Keyword `model_ttft` **222ms faster** with **larger** payload | Payload savings do **not** outweigh embed RTT at this catalog size |
| Gate default **40** was estimated at **26-tool** catalog | **Too low** for current prod connected set (70 tools) |
| Warm embed still ~250–500ms `narrow_tools_ms` | Even warmed, may not beat keyword unless catalog grows much larger |

**Recommendation (evidence-backed):** ~~Raise threshold~~ **Shipped 2026-07-24** — default **200** (see Shipped section).

## 4 — Same-conversation cache test (keyword path — winner)

After A/B, cache test on keyword path (`embed_min=999`): `unified-turn-task-ttft-70tools-keyword-same-conversation-cache.json`

| Probe | Turn | cache ratio | `model_ttft_ms` |
|-------|------|-------------|----------------:|
| email_intent | 1 | 95.6% | 1066 |
| email_intent | 2 | 52.3% | **665** (−401) |
| deals_status | 1 | 84.3% | 638 |
| deals_status | 2 | 84.2% | 583 (−55) |

Turn-1 already had high prefix cache (static system + warm fleet). Turn-2 still improves TTFT on email_intent (−401ms). Prefix caching works; retrieval path choice is the separate bottleneck.

## Shipped (2026-07-24)

**Config:** `UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS` default raised **40 → 200** (`backend/app/config.py`).

> Embedding tool-retrieval measured WORSE than keyword at both 26 and 70 connected tools. No catalog size has yet shown a win. Threshold raised as a placeholder, not because a new crossover was found — revisit only if a future measurement shows real benefit.

At prod catalog ~70 tools, unified task turns stay on **keyword** narrow until catalog ≥ 200. Standing cache baseline: [`unified-turn-task-ttft-keyword-cache-standing-baseline.json`](unified-turn-task-ttft-keyword-cache-standing-baseline.json) (`ceb9081b…`, `embed_min=200`).

| Probe | Turn 1 `model_ttft_ms` | Turn 2 | Δ | `retrieval_method` |
|-------|------------------------|--------|---|-------------------|
| email_intent | 1258 (0% cache) | 964 | **−294** | keyword |
| deals_status | 721 (52% cache) | 761 | +40 | keyword |

Prefix-cache win on email_intent turn-2 holds (−294ms); deals_status turn-2 flat (+40ms) at this sample.

## Post-fix latency (2026-07-24, `9496cedf`)

Real fix shipped: shared OpenAI client, batch tool-doc embeds, parallel query+docs, await boot warm, Phase 0 sub-timings. Full write-up: [`unified-turn-embed-latency-fix-2026-07-24.md`](unified-turn-embed-latency-fix-2026-07-24.md).

| Path | `narrow_tools_ms` | `embed_query_ms` | `model_ttft_ms` | wall |
|------|------------------:|-----------------:|----------------:|-----:|
| Embedding pre-fix | 1048 | — | 1024 | 2073 |
| **Embedding post-fix** | **434** | **427** | 830 | 1269 |
| Keyword (same tip) | 1 | — | 837 | 840 |

**Threshold stays 200** — fix cut embed overhead ~59% but keyword still wins end-to-end at 70 tools.

## Scripts

- `scripts/verify-unified-turn-task-ttft-live.py` — `TTFT_SKIP_FOLLOW_UP=1`, `unified_live_probes` summary
- `scripts/apply-railway-unified-turn-embed-gate.ps1` — toggle keyword vs embedding for live A/B
