# Voice latency Phases 0–6 — live evidence

**Tip:** `dc2590908b4a9e24b730c203eb3f589ef785584e` (`/health` 2026-08-14)  
**Artifacts:** `voice-latency-phase0-baseline-live.json`, `voice-latency-phases-live.json`, `voice-latency-phase6-uncached-live.json`

## Phase 0 — before optimize (tip `6b64c366`)

| Probe | TTFT | TTFA |
|-------|-----:|-----:|
| User-stated One Brain voice baseline | 4632 | 4813 |
| Live simple “2+2” | 5494 | null* |
| Live simple “Gravitre does” | 4302 | null* |

\*Short-answer TTFA null: sentence splitter required trailing whitespace; `turn.complete` before TTS flush — fixed.

**Critic on every turn?** Pre-ACT VERIFY is noop without draft (`pre_act_no_draft`). Post-delivery critic LLM ran on answers ≥40 chars even when not mandatory. Unified LIVE finished the full model call before any voice text (batch emit).

## What shipped (same CognitiveTurnKernel — not a second brain)

1. **Tiered depth** — spoken defaults `mode=fast`; `reasoning_depth=conversational` skips Knowledge Fabric merge + non-mandatory critic; writes escalate to `standard` + `full` + mandatory critic.
2. **Speculative STT** — FE starts turn on high-confidence Deepgram interim; cancel/restart via existing Redis barge-in cancel if final diverges.
3. **Prefix cache** — same OpenAI path; live voice turns report `cached_prompt_tokens` / ratio.
4. **Fast-tier model** — simple voice uses `gpt-5.4-mini` (`effective_mode=fast`, `routing_tier=simple`).
5. **E2E streaming** — spoken unified LIVE forwards model text deltas to SSE/TTS as they arrive (not batch-then-speak).

## Phase 6 — after (tip `dc259090`)

### A) Battery including tier0/cache hits (`voice-latency-phases-live.json`)

| Probe | TTFT | TTFA | Depth |
|-------|-----:|-----:|-------|
| simple | **1385** | **1564** | (tier0/`cache` early path) |
| simple turn2 | **1008** | **1201** | (tier0/`cache`) |
| write-shaped | **2583** | **2773** | **full** |

Δ vs 4632/4813 on simple: **−3247 / −3249 ms** when tier0 hits.

### B) Uncached nonce probes (`voice-latency-phase6-uncached-live.json`)

| Probe | TTFT | TTFA | Depth | Notes |
|-------|-----:|-----:|-------|-------|
| simple1 | 4778 | 5012 | conversational | KNOWLEDGE **0ms**; cache tokens 3712 (62%) |
| simple2 | 4593 | 4861 | conversational | cache tokens 4224 (69%) |
| write | 3166 | 3354 | **full** | KNOWLEDGE **774ms**; confirm gate |

Cold conversational stays in the ~4.5–4.8s class (near the 4632 baseline), not the old 700–900 half-duplex benchmark. Largest remaining cost is model TTFT + RECALL after lighter stages.

### Per-lever honesty

| Lever | Measured effect |
|-------|-----------------|
| Tiered depth / skip KNOWLEDGE | Confirmed: conversational KNOWLEDGE=0; write KNOWLEDGE≈530–774ms |
| Skip non-mandatory critic | Confirmed for conversational classical path; unified conversational has no post-critic wait |
| Speculative STT | Wired (FE); API probes do not measure interim STT savings |
| Prefix cache on voice | Confirmed cache hits (62–69% cached prompt tokens on multi-turn) |
| Fast-tier model | Confirmed `gpt-5.4-mini` / `fast` on simple |
| Stream unified→TTS | Confirmed TTFA ≈ TTFT+150–250ms; short answers now speak |
| Tier0/cache early path | Large win when hit (~1.0–1.4s TTFT) — same text tier0, not a voice fork |

### Governance

Write-shaped turns keep **full** depth, Knowledge merge, and confirm/approval path (`retrieve_plan_gate` / awaiting confirm). Speed on simple turns came from tiering + streaming + cache — not from skipping write governance.
