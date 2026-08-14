# Voice latency — Phase 0 baseline (pre-optimization)

Measured live against tip `6b64c366…` on 2026-08-14 before the latency optimization deploy.

Artifact: [`voice-latency-phase0-baseline-live.json`](voice-latency-phase0-baseline-live.json)

## Aggregate (user-stated prior)

| Metric | User-stated One Brain voice baseline | Half-duplex prior |
|--------|--------------------------------------:|------------------:|
| TTFT | ~4632 ms | ~700–900 ms |
| TTFA | ~4813 ms | (same class) |

## Fresh live probes @ tip `6b64c366` (unified LIVE=true)

| Probe | TTFT ms | TTFA ms | Notes |
|-------|--------:|--------:|-------|
| warm check-in | 12347 | 12565 | Tool rounds + long reply |
| simple “two plus two” | **5494** | null* | Matches ~4.6–5.5s class |
| simple “what Gravitre does” | **4302** | null* | Closest to stated 4632 |

\*TTFA null on short answers was a measurement/path bug: `split_speakable_chunks` required trailing whitespace after `.!?`, and `voice.turn.complete` fired before TTS flush — fixed in the optimization tip.

## Stage attribution (code + live shape; instrumented on opt tip)

| Stage | On every voice turn pre-opt? | Blocks first text? | Evidence |
|-------|------------------------------|--------------------|----------|
| STT finalization | Client-side (outside session TTFT clock) | No (clock starts at session/turn) | `voice_session_service.stream_voice_turn_events` |
| Memory RECALL | Yes (CognitiveTurnKernel) | Yes | Kernel always runs pre-ACT |
| Knowledge Fabric merge | Yes | Yes | `merge_knowledge` on critical path |
| PLAN / metrics / what-if | Yes (heuristic + optional sim) | Yes | Kernel PLAN stage |
| Pre-ACT VERIFY critic LLM | **No** — noop without draft; marks `mandatory_pending_post_act` for writes | No | `_verify` → `pre_act_no_draft` |
| Model TTFT | Yes | Yes | Unified LIVE completes full answer then one `text-delta` |
| Post-stream critic LLM | **Yes for answers ≥40 chars** even when not mandatory | **After** text on classical; **before** any text on unified LIVE | `verify_before_delivery` |
| TTS TTFA | After first speakable chunk | After TTFT + TTS RTT | Sentence buffer + ElevenLabs |

### Critic-on-every-turn confirmation

**Pre-ACT mandatory critic does not run an LLM on every voice turn** (noop without draft).

**Post-delivery critic did run an LLM on non-write answers ≥40 characters** whenever the classical path finished — including low-stakes conversational turns that never needed it. Unified LIVE also finished the full model call (+ tools) before any voice text/audio, which dominated TTFT (~4.3–5.5s on simple probes).

Largest levers confirmed: (1) tiered depth / skip non-mandatory critic + heavy KNOWLEDGE on simple spoken, (2) skip unified LIVE batch-emit for conversational spoken so progressive TTS can start, (3) fix short-answer TTS flush, (4) speculative interim STT, (5) same OpenAI prefix cache path on multi-turn voice.
