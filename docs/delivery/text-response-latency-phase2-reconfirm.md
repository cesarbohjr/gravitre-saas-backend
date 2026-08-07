# Text-response latency — Phase 2 reconfirm shipped wins (closed)

**Status:** DONE on tip `8c21d5c1` (API `/health` at probe time).  
**Checked:** 2026-08-06  
**Artifacts:** `unified-turn-task-ttft-phase2-reconfirm.json`, `a5d-extension-progressive-live.json`

## 1. Model-tier routing (LIVE)

Task/mixed probes selected **`gpt-5.4-mini`** with `task_model_tier: "low"` and `turn_shape_hint: "task_shaped"`:

| Probe | Model | Tier |
|-------|-------|------|
| email_intent | gpt-5.4-mini | low |
| apollo_list_write | gpt-5.4-mini | low |
| hubspot_search | gpt-5.4-mini | low |
| deals_status | gpt-5.4-mini | low |

Health: `unified_turn_live_enabled: true`. No tier regression.

## 2. Prefix / prompt caching (turn-2 vs turn-1)

Exact same-conversation cache probes:

| Probe | Turn-1 ratio / TTFT | Turn-2 ratio / TTFT | Δ TTFT |
|-------|---------------------|---------------------|--------|
| email_intent | **0.987** / 2566ms (3200 cached toks) | 0.8421 / **504ms** | **-2062ms** |
| deals_status | 0.5182 / 815ms (1664 cached) | 0.4579 / 825ms | +10ms |

Cache is live: email turn-1 hit ~99% prefix cache; turn-2 first-token dropped to 504ms.

## 3. Progressive disclosure + local MiniLM (A1/A7 + A5d)

**A1/A7** (`POST` assistant chat via TTFT battery):

| Probe | progressive_disclosure | embed_query_method | embed_query_model | narrow_tools_ms | model_ttft_ms |
|-------|------------------------|--------------------|-------------------|-----------------|---------------|
| email_intent | true | local | all-MiniLM-L6-v2 | **10** | 2566 |
| apollo_list_write | true | local | all-MiniLM-L6-v2 | 697* | 689 |
| hubspot_search | true | local | all-MiniLM-L6-v2 | **10** | 540 |
| deals_status | true | local | all-MiniLM-L6-v2 | **12** | 815 |

\*697ms narrow on apollo is a cold MiniLM encode outlier (Phase 3 tail candidate), not a keyword fallback.

**A5d** (`/api/extension/chat`): `progressive_disclosure_confirmed: true`, `embed_query_method: local`, `retrieval_method: embedding_narrow_tools_for_turn` on `ext_email_stubs`. Pass.

**A2** shares A1 `/api/chat` path (routing map) — same LIVE gate; no separate chip path.

## Battery summary (not the standing gate)

- wall TTFT p50 **1357ms**, min 516, max **2579**
- model TTFT p50 **752ms**
- Functional 4/5: `apollo_list_write` functional_ok=false (fallthrough + already-created list vs awaiting_confirm expectation) — **not** a tier/cache/MiniLM regression

## Verdict

All three previously-shipped latency wins are **genuinely live** on tip `8c21d5c1`. No fix required in Phase 2.
