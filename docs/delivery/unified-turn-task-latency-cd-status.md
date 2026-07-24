# Unified turn — task-shaped latency (C embedding + D model tier)

Updated: 2026-07-23  
Tip (final measure): `182b91b3…` · `UNIFIED_TURN_TASK_MODEL_TIER=low` · LIVE=true

## Pending LIVE + Module B (2026-07-23)

**Deliberate scoped exception:** When `has_pending_family`, unified LIVE runs `classify_pending_reply` **before** the single reasoning call and may return formatted hold/abandon/meta/ambiguous copy without invoking the model — this is **not** a return to general classify-then-route; task-shaped turns without pending still use one unified reasoning call only.

**Rationale (one line):** Pending interrupt semantics are safety-critical and already owned by Module B; deterministic classification prevents LIVE from bypassing hold/abandon while the rest of the turn stays unified.

---

## Scope

- **Metric:** task-shaped / mixed TTFT — not social greetings.
- **C:** embedding tool retrieval for task/mixed when connected catalog ≥ `UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS` (default **200**, shipped 2026-07-24). Below that, keyword.
  - **Gate threshold provenance:** Embedding tool-retrieval measured **WORSE than keyword** at both **26** and **70** connected tools. No catalog size has yet shown a win. Default **200** is a placeholder — not because a new crossover was found; revisit only if a future measurement shows real benefit. (Prior default **40** was an estimate at 26 tools, never empirically validated.)
- **D:** `UNIFIED_TURN_TASK_MODEL_TIER` for task/mixed. Empty → `gpt-4o-mini`; `low` → `gpt-5.4-mini`.
- Shape hint selects retrieval/model only — **reasoning call always runs** (Option A rejected).

## Before / after (live)

### Baseline — keyword + `gpt-4o-mini` (tip `1c0eee8e…`)

Artifact: [`unified-turn-task-ttft-baseline-keyword.json`](unified-turn-task-ttft-baseline-keyword.json)

| Probe | model_ttft_ms | visible | payload_b | functional |
|-------|--------------:|--------:|----------:|:----------:|
| email_intent | 560 | 13 | 5093 | ok |
| apollo_list_write | 671 | 13 | 5093 | ok |
| hubspot_search | 711 | 3 | 1044 | ok |
| deals_status | 1051 | 13 | 4965 | ok |
| mixed_hey_apollo | 470 | 13 | 5093 | ok |

- wall / model p50: **673 / 671**
- functional: **5/5**

### After C — embedding forced on 26-tool catalog (tip `8ebe81e2…`, warm)

Artifact: [`unified-turn-task-ttft-after-embed-warm.json`](unified-turn-task-ttft-after-embed-warm.json)

| Probe | model_ttft_ms | wall | retrieval | payload_b | functional |
|-------|--------------:|-----:|-----------|----------:|:----------:|
| email_intent | 495 | 798 | embedding | 4346 | ok |
| apollo_list_write | 488 | 780 | embedding | 4179 | ok |
| hubspot_search | 425 | 871 | embedding | 5789 | ok |
| deals_status | 634 | 946 | embedding | 4206 | ok |
| mixed_hey_apollo | 398 | 686 | embedding | 4179 | ok |

- wall / model p50: **798 / 488**
- functional: **5/5** (cold first pass had 4/5 flaky Apollo connect copy; warm 5/5)
- **Finding:** `model_ttft` improved (~671→488) via slightly smaller schemas; **wall worsened** because each turn pays OpenAI **query-embed** RTT (~300ms) in `narrow_tools_ms`. On a 26-tool connected set that overhead dominates.

**Mitigation shipped:** skip embedding when `total_tools < UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS` (default **200** as of 2026-07-24). At prod ~70 tools, keyword narrow is the live path. See [`unified-turn-retrieval-ab-70tools-2026-07-24.md`](unified-turn-retrieval-ab-70tools-2026-07-24.md).

Cold-start evidence (first request after deploy): wall 6196 / 4899 with `narrow_tools_ms` 4–4.5s while tool vectors cache — [`unified-turn-task-ttft-after-embed.json`](unified-turn-task-ttft-after-embed.json).

**Startup warm (2026-07-23):** `warm_tool_document_embeddings()` runs on app lifespan (background thread) when AI enabled — pre-populates `_TOOL_EMBED_CACHE` so large-catalog embedding path avoids first-request cold embed storm. Keyword path on small catalogs unchanged.

### After D — keyword (catalog&lt;40) + `gpt-5.4-mini` (tip `182b91b3…`, tier=low)

Artifact: [`unified-turn-task-ttft-after-embed-gate-or-low-tier.json`](unified-turn-task-ttft-after-embed-gate-or-low-tier.json)

| Probe | model_ttft_ms | wall | model | retrieval | functional |
|-------|--------------:|-----:|-------|-----------|:----------:|
| email_intent | 436 | 438 | gpt-5.4-mini | keyword | ok |
| apollo_list_write | 429 | 430 | gpt-5.4-mini | keyword | ok |
| hubspot_search | 451 | 453 | gpt-5.4-mini | keyword | ok |
| deals_status | 456 | 457 | gpt-5.4-mini | keyword | ok |
| mixed_hey_apollo | 413 | 414 | gpt-5.4-mini | keyword | ok |

- wall / model p50: **438 / 436**
- functional: **5/5** (same battery as baseline)

## Verdict

| Work | Result |
|------|--------|
| **C embedding** | **Built; gated off at prod catalog size.** Measured worse than keyword at 26 and 70 tools. Default min catalog **200** (2026-07-24) — placeholder, not a measured crossover. |
| **D model tier `low`** | **PASS** — same 5/5 functional; task model_ttft p50 **671→436ms** (~35% faster); wall p50 **673→438ms**. Kept on prod (`UNIFIED_TURN_TASK_MODEL_TIER=low`). |

## Settings

| Env | Default | Meaning |
|-----|---------|---------|
| `UNIFIED_TURN_EMBEDDING_TOOL_RETRIEVAL` | `true` | Enable semantic path when catalog large enough |
| `UNIFIED_TURN_EMBED_MIN_CATALOG_TOOLS` | `200` | Below → keyword; 200 = placeholder (no measured embed win yet) |
| `UNIFIED_TURN_TASK_MAX_TOOLS` | `16` | Cap for task-shaped |
| `UNIFIED_TURN_TASK_MODEL_TIER` | `low` in prod after D | `MODEL_TIERS` key; empty → `gpt-4o-mini` |

## Scripts

```bash
TTFT_LABEL=baseline-keyword python scripts/verify-unified-turn-task-ttft-live.py
TTFT_LABEL=after-embed-warm python scripts/verify-unified-turn-task-ttft-live.py
TTFT_LABEL=after-low-tier python scripts/verify-unified-turn-task-ttft-live.py
```
