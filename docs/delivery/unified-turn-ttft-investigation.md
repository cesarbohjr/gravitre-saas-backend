# Unified turn TTFT investigation (200ms gate)

Updated: 2026-07-23  
Status: **instrumented live re-measure complete; 200ms gate remains MISS**

Artifact: [`unified-turn-ttft-breakdown-live.json`](unified-turn-ttft-breakdown-live.json)  
Tip: `6457ba7c…` · `/health` live=true @ `2026-07-23T05:14:31Z`

## 1) Where the ~481ms goes (instrumented)

`first_token_proxy_ms` previously mixed assembly + model. New `latency_breakdown` splits them.

| Message | wall TTFT | `model_ttft_ms` | `pre_model_ms` | Evidence |
|---------|----------:|----------------:|---------------:|----------|
| Hey | 494 | **492** | 0 | `unified_turn.live.completed` @ `2026-07-23T05:14:35.04788Z` conv `0df67710…` |
| Thank you | 749 | **746** | 1 | @ `05:14:45.059866Z` conv `d0b64a27…` |
| What's on your plate? | 546 | **545** | 0 | @ `05:14:51.268529Z` conv `2ef23add…` |

**Verdict:** p50 wall ≈ **546ms**; nearly 100% is **OpenAI stream TTFT** (`model_ttft_ms`). Context assembly / keyword narrow / registry are **≤1ms**. Not network residual inside our process (`pre_first_token_overhead_ms` 2–3ms).

Also in audits: `system_prompt_chars≈8811`, `messages_chars≈9232`, `tools_payload_bytes=4965`.

## 2) Full 600+ catalog every call?

**No. Rejected.**

| Check | Result |
|-------|--------|
| Retrieval | `keyword_narrow_tools_for_turn` — **not** embedding (`embedding_tool_retrieval=false`) |
| Live tools | `totalTools=26` → `visibleTools=13` (Apollo-focused) |
| Payload | **4965** bytes sent vs **14367** bytes full connected set (still not 600+) |
| Phase 0 | Embedding retrieval listed as Future; keyword narrow chosen now |

Large-catalog-every-call is **not** the cause. Remaining model cost is a tool-aware call with ~13 compressed schemas + ~8.8k Module D system prompt.

## 3) Fair baseline (classical vs unified)

Same tip-class social queries on classical conversational path:

| Message | Classical path | Classical total |
|---------|----------------|----------------:|
| Hey | heuristic + **phrase bank**, no LLM | **~0–20ms** |
| Thank you | same | **~0ms** |
| What's on your plate? | task_shaped (not social bank) | classify may use LLM (~0.9s on operator host) — different class |

**Explicit tradeoff:** Unified LIVE always runs a streamed tool-aware model call, even for greetings. Classical social was a local bank (no tools, usually no LLM). The ~500ms+ is largely “unified does real model reasoning with tools”; classical social did less. That is a product tradeoff, not silent infra debt.

## 4) Fix plan (gate stays MISS until post-fix re-measure)

Do **not** claim TTFT PASS until `model_ttft_ms` p50 &lt;200 **or** the target is explicitly revised.

| Option | Change | Why |
|--------|--------|-----|
| **A. Social short-circuit under LIVE** | Heuristic greeting/thanks → phrase bank (classical); unified tools call only for task-shaped | Directly restores social TTFT; write path unchanged |
| **B. Zero tools on social** | `tools=[]` when heuristic conversational | Cuts ~5KB schemas; may shave model TTFT but unlikely alone to hit 200ms |
| **C. Embedding tool retrieval** | Phase 0 Future semantic top-k | Relevance at 600+; not the social-TTFT fix |
| **D. Model tier** | Faster model for unified | Direct `model_ttft_ms` lever for task turns |

**Recommended:** implement **A** (optionally **B**), redeploy, re-run `scripts/verify-unified-turn-ttft-breakdown-live.py`. Expect social wall/`model_ttft` to collapse toward classical; keep measuring task-shaped turns separately against a realistic target.

## Gate status

| Gate | Status |
|------|--------|
| TTFT &lt;200ms | **MISS** — model_ttft p50 ~546ms |
| Full-catalog hypothesis | **REJECTED** |
| Classical fair compare | **Documented** — bank ≪ unified for social |
| Instrumentation | **PASS** — tip `6457ba7c` emits `latency_breakdown` |

Rollback (cutover, unrelated): `UNIFIED_TURN_LIVE_ENABLED=false` + redeploy.
