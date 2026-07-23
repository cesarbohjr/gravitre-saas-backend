# Unified turn — task-shaped latency (C embedding + D model tier)

Updated: 2026-07-23

## Scope

- **Metric:** task-shaped / mixed TTFT (`model_ttft_ms` / wall), not social greetings.
- **C:** embedding tool retrieval for task/mixed only (heuristic shape hint selects retrieval strategy; reasoning call always runs).
- **D:** `UNIFIED_TURN_TASK_MODEL_TIER` for task/mixed (empty = historical `gpt-4o-mini`).
- Social turns keep keyword narrow + default model (Option A rejected).

## Baseline (before) — tip `1c0eee8e…`

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
- retrieval: `keyword_narrow_tools_for_turn`
- model: `gpt-4o-mini`

## After C / D

_Filled after tip with embedding retrieval (+ optional task model tier) is live._

## Settings

| Env | Default | Meaning |
|-----|---------|---------|
| `UNIFIED_TURN_EMBEDDING_TOOL_RETRIEVAL` | `true` | Semantic top-k for task/mixed |
| `UNIFIED_TURN_TASK_MAX_TOOLS` | `16` | Cap when task-shaped |
| `UNIFIED_TURN_TASK_MODEL_TIER` | `""` | `low` → `gpt-5.4-mini` via `MODEL_TIERS`; empty → `gpt-4o-mini` |

## Scripts

```bash
TTFT_LABEL=baseline-keyword python scripts/verify-unified-turn-task-ttft-live.py
TTFT_LABEL=after-embed python scripts/verify-unified-turn-task-ttft-live.py
TTFT_LABEL=after-embed-low-tier python scripts/verify-unified-turn-task-ttft-live.py
```
