# Unified turn TTFT investigation (200ms gate)

Updated: 2026-07-23  
Status: **instrumentation ready to ship; live phase breakdown pending tip with `latency_breakdown`; 200ms gate remains MISS**

## Questions answered

### 1) Where does ~481ms p50 go?

**Prior metric caveat:** `first_token_proxy_ms` is wall-clock from *unified-turn start* (registry + narrow + prompt assembly **included**) to first stream delta — not pure model TTFT.

New instrumentation writes `latency_breakdown` on `unified_turn.*.completed` audits:

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

Re-measure: `scripts/verify-unified-turn-ttft-breakdown-live.py` → [`unified-turn-ttft-breakdown-live.json`](unified-turn-ttft-breakdown-live.json).

**Pre-instrumentation live samples** (tip `c81d1200`, wall TTFT only):

| Message | `first_token_proxy_ms` | Audit `tool_stats` | Evidence |
|---------|-----------------------:|--------------------|----------|
| Hey | 1121 | totalTools **26**, visibleTools **13** | `unified_turn.live.completed` @ `2026-07-23T01:58:46.788615Z` conv `ea672d1a…` |
| Thank you | 396 | same | @ `01:58:55.237898Z` conv `3580fea3…` |
| What's on your plate? | 407 | same | @ `01:59:02.966519Z` conv `013a8d92…` |

Wall TTFT p50 **407ms** (≫200ms). `latency_breakdown` empty until instrumented tip is live.

Assembly cost offline: `narrow_ms` 0–1ms — **not** the dominant term. Dominant term is the model stream (to be confirmed as `model_ttft_ms` after tip advance).

### 2) Full 600+ catalog every call?

**No.** Embedding-based retrieval was **not** implemented.

| Fact | Evidence |
|------|----------|
| Phase 0 decision | [unified-turn-reasoning-phase0.md](unified-turn-reasoning-phase0.md) §4: keyword `narrow_tools_for_turn`; embedding “Future” |
| Code | `run_unified_turn_shadow` → `narrow_tools_for_turn` (token overlap + connector focus, cap default **32**) |
| Live prod | `visibleTools=13` / `totalTools=26` (Apollo-focused connected set) — not 600+ |
| Offline (5 connectors) | 93 → 28 visible; ~10KB vs ~50KB full connected payload |

Hypothesis “full catalog every call causes TTFT” is **rejected**. Remaining cost is still a **tool-aware streamed model call** (~13 schemas + Module D system prompt) versus classical bank.

### 3) Fair baseline vs old classify-then-route

For **Hey / Thank you** (the social class in the 481ms sample):

| Path | What it does | Measured |
|------|----------------|----------|
| **Classical conversational** | `heuristic_turn_shape` → phrase-bank `generate_conversational_reply` | **0–6ms** total; `path=phrase_bank_no_llm`; no tool schemas |
| **Unified LIVE** | Always one streamed OpenAI call with narrowed tools + Module D system spec | Wall TTFT **396–1121ms** |

Artifact: `classical_baseline` in [`unified-turn-ttft-breakdown-live.json`](unified-turn-ttft-breakdown-live.json).

**Explicit tradeoff:** 481ms is not “infra cost of doing this properly” versus an equally tool-aware classical social path. Classical social was intentionally cheap (local bank). Unified pays for one reasoning call with tools on every turn, including greetings. That is a product tradeoff to discuss — not silently absorb.

Note: “What's on your plate?” is **task_shaped** on classical (classify ~1009ms on operator host when heuristic misses) — different class than greeting/thanks.

### 4) Fix plan (gate stays MISS until post-fix re-measure)

Do **not** mark TTFT PASS until tip shows target met (or target is explicitly revised).

| Option | Change | Rationale |
|--------|--------|-----------|
| **A. Social short-circuit under LIVE** | Heuristic greeting/thanks → phrase bank (or no-tools micro-completion); unified tools call only for task-shaped | Restores classical social TTFT; keeps write path on unified |
| **B. Smaller / zero tools on social** | `tools=[]` when heuristic conversational; or lower max_tools | Cuts schema tokens → `model_ttft_ms` |
| **C. Embedding tool retrieval** | Phase 0 “Future” semantic top-k | Relevance at 600+ scale; unlikely to beat bank for greetings |
| **D. Model tier** | Faster model for unified social-capable turns | Direct `model_ttft_ms` lever |

Recommended: **A + B**, then re-run breakdown probe; only then consider C/D for task turns.

## Rollback

`UNIFIED_TURN_LIVE_ENABLED=false` + redeploy.

## Gate status

| Gate | Status |
|------|--------|
| TTFT &lt;200ms | **MISS** |
| Full-catalog hypothesis | **REJECTED** |
| Classical fair compare (social) | **Documented** — bank ≪ unified |
| Phase split (`model_ttft_ms`) | **PENDING** tip with instrumentation |
