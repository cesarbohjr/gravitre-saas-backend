# Unified turn TTFT investigation (200ms gate)

Updated: 2026-07-23  
Status: **instrumentation shipped; live phase breakdown pending tip with `latency_breakdown`; 200ms gate remains MISS**

## Questions answered

### 1) Where does ~481ms p50 go?

**Prior metric caveat (important):** `first_token_proxy_ms` was wall-clock from *unified-turn start* (registry + narrow + prompt assembly **included**) to first stream delta — not pure model TTFT.

New instrumentation (tip after this commit) writes `latency_breakdown` on `unified_turn.*.completed` audits:

| Key | Meaning |
|-----|---------|
| `registry_tools_ms` | `get_tools_for_agent` |
| `narrow_tools_ms` | keyword `narrow_tools_for_turn` |
| `context_prompt_ms` | pending context + Module D system prompt + message assembly |
| `pre_model_ms` | sum of above (before OpenAI `create`) |
| `model_ttft_ms` | OpenAI `create` start → first content/tool-call delta |
| `wall_to_first_token_ms` | same as historical `first_token_proxy_ms` |
| `tools_payload_bytes` / `visible_tools` | schemas actually sent |
| `full_catalog_payload_bytes` / `total_tools` | hypothetical full connected catalog (not sent) |
| `retrieval_method` | always `keyword_narrow_tools_for_turn` |
| `embedding_tool_retrieval` | always `false` |

Re-measure script: `scripts/verify-unified-turn-ttft-breakdown-live.py` → [`unified-turn-ttft-breakdown-live.json`](unified-turn-ttft-breakdown-live.json).

**Pre-instrumentation live samples** (tip `c81d1200`, wall TTFT only): Hey 1121 / Thank you 396 / What's on your plate 407 → rough p50 **407ms** (still ≫200ms).

### 2) Full 600+ catalog every call?

**No — full catalog is not sent.** Embedding-based retrieval was **not** implemented.

| Fact | Evidence |
|------|----------|
| Phase 0 decision | [unified-turn-reasoning-phase0.md](unified-turn-reasoning-phase0.md) §4: retrieval via `narrow_tools_for_turn`, embedding “Future” |
| Code path | `unified_turn_reasoning_service.run_unified_turn_shadow` → `narrow_tools_for_turn` (token overlap + connector focus, cap `UNIFIED_TURN_SHADOW_MAX_TOOLS` default **32**) |
| Offline sizing (operator host) | See artifact `catalog_offline` — keyword narrow only; `embedding_tool_retrieval=false` |

So the 481ms miss is **not** “600 schemas every call.” It can still be driven by **tens of compressed schemas + large Module D system prompt + model time**.

### 3) Fair baseline vs old classify-then-route

For **Hey / Thank you** (monitor’s social class):

| Path | What it does | Cost |
|------|----------------|------|
| **Classical conversational** | `heuristic_turn_shape` → `generate_conversational_reply` → **Module D phrase bank** | Local only — **no tool schemas, usually no LLM** |
| **Unified LIVE** | Always one streamed OpenAI call with narrowed tools + full Module D system spec | Network + model TTFT (hundreds of ms) |

Measured classical baseline (operator host, same messages): see artifact `classical_baseline` — heuristic hit, phrase-bank path, **total_ms ≈ 0–few ms**.

**Explicit tradeoff:** 481ms is not “the cost of doing this properly” vs an equally tool-aware classical social path. Classical social was intentionally cheap (bank). Unified pays for one reasoning call with tools on every turn, including greetings. That is an expected product tradeoff to discuss — not silently absorb as infra noise.

Task-shaped classical turns (mapper / ReAct) are a different baseline and were not the 481ms sample class.

### 4) Fix plan (200ms gate stays MISS until re-measure)

Do **not** mark TTFT PASS until a post-fix tip shows `model_ttft_ms` p50 &lt;200 **or** a revised target is explicitly accepted.

| Option | Change | Rationale |
|--------|--------|-----------|
| **A. Social short-circuit under LIVE** | For pure greeting/thanks (same heuristic as classical), serve phrase-bank / tiny no-tools completion; keep unified tools call for task-shaped | Restores classical social TTFT; keeps write path on unified |
| **B. Smaller tool payload** | Lower `UNIFIED_TURN_SHADOW_MAX_TOOLS` for conversational; strip tools entirely when heuristic says conversational | Cuts schema tokens → model TTFT |
| **C. Embedding tool retrieval** | Replace keyword narrow with semantic top-k (Phase 0 “Future”) | Better relevance at 600+; may not beat bank path for social |
| **D. Model tier** | Faster / smaller model for unified social-capable turns | Direct model_ttft lever |

Recommended sequence: **A + B** first (product-correct for greetings), re-measure `model_ttft_ms` + wall TTFT on tip; only then consider C/D for task turns.

## Rollback

Unrelated to TTFT: `UNIFIED_TURN_LIVE_ENABLED=false` + redeploy.

## Gate status

| Gate | Status |
|------|--------|
| TTFT &lt;200ms | **MISS** — do not claim pass |
| Instrumentation | **PASS** once tip includes `latency_breakdown` and probe `instrumentation_present=true` |
| Catalog-full hypothesis | **REJECTED** (narrowed keyword subset) |
| Classical fair compare | **Documented** — bank path ≪ unified for social |
