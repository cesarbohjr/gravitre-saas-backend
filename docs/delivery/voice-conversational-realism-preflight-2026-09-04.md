# Conversational-realism layer — MANDATORY PRE-FLIGHT result: FAILED

**Date:** 2026-09-04
**Deployed tip checked:** `20bf932fc48903c10f95a15e5d8ccc984bef5ec6` (confirmed live via `GET https://api.gravitre.app/health` → `git_sha`, and via HEAD on `main` matching)

## Pre-flight question (verbatim from the conversational-realism prompt)

> "confirm the speed/latency standard prompt has shipped and been human-verified first. This layer depends on a genuinely responsive base pipeline to be meaningfully tested; building conversational realism on top of a still-broken, high-latency pipeline would make it impossible to tell which layer a new problem belongs to."

## Result: **FAILED — do not proceed to Phase 1–6 builds**

Two independent conditions were required. Neither is met.

### 1. "Shipped" — partially true, but the pipeline is not fast

What *has* shipped and is live at `20bf932f`:
- Text-corruption fix (`period.between.every.word`) in `cognitive_llm.py` — chunked, sentence-boundary normalization instead of per-delta.
- Jargon-leak / forced-repeat fix in `unified_turn_reasoning_service.py` — silent auto-retry of `search_catalog_tools` instead of surfacing `full_schema_not_loaded` / asking the user to repeat themselves.
- Per-stage `data-intelligence` latency logging added to `cognitive_llm.py` (log-only, Railway logs).

What has **not** shipped: any actual latency fix. Re-running the same live probe (`scripts/measure-voice-pipecat-live-latency.py`, synthesized speech → `wss://api.gravitre.app/api/voice/pipecat/ws`, real ElevenLabs audio in, real Deepgram+TTS round trip) against `20bf932f` today:

| Scenario | P50 | P95 | Target (P95) | Met? |
|---|---|---|---|---|
| simple_conversational (n=5) | 7,000 ms | 8,168.6 ms | 500 ms | **NO — 16x over** |
| consequential_write_shaped (n=3) | 15,056 ms | 17,828.9 ms | 500 ms | **NO — 35x over** |

Raw output: `docs/delivery/voice-pipecat-live-latency-2026-09-04.json`

**New finding from the just-deployed instrumentation** (Railway logs, `pipecat_voice_turn_latency`, live turns from this probe run): the bottleneck is not STT and not TTS.
- TTS first-byte: 120–250 ms (confirmed fast, not the problem).
- Cognitive stages accounted for by the router (`RECALL` + `PLAN`) sum to only **~1.6 s**.
- But `first_text_delta_ms` — time from turn start to the LLM's first streamed token — lands at **12,354–14,935 ms** across the sampled turns just captured live.
- That means **~8–13 s per turn is currently unaccounted for** by any existing stage timer between the initial routing decision and the LLM actually starting to stream. The `data-intelligence` event fires multiple times per turn with a growing `pre_llm_ms` and no stage detail on the later firings — this is itself evidence the current instrumentation is insufficient to name the exact culprit (retry loop, serialized network round-trip, queuing, etc. — unconfirmed) and needs dedicated root-causing before any conversational-realism work can be meaningfully attributed to the right layer.

Conclusion: the speed/latency standard is **not shipped in the sense that matters** — end users still wait 7–18 seconds for a first word, unchanged from the original complaint. Instrumentation improved; actual latency did not.

### 2. "Human-verified" — not met

No `HUMAN_VOICE_CONFIRM 2026-09-04` has been received from the user. Per the standing rule from the prior gate (`d33a2cce`), automated probe PASS results (WebSocket connects, HTTP duplex, synthesized-speech-in-probe latency numbers) are infrastructure evidence only and do **not** constitute human-experience verification. That checklist is still open:
`docs/delivery/voice-pipecat-human-verify-and-opt-inventory-2026-09-04.md`

## Read-only Phase 0 audit performed anyway (no mutation — answers the prompt's own Phase 0 questions honestly, does not start Phase 1 build)

**Q1 — Does any user speech during AGENT_SPEAKING stop playback unconditionally, or is there already real backchannel-vs-interruption classification?**

Confirmed by code read, not assumption: the **live** Pipecat WS path (`backend/app/services/pipecat_voice/pipeline.py`, the `default_orchestration=pipecat` production path) constructs its `PipelineTask` with:

```1_1:pipeline.py
PipelineParams(
    enable_metrics=True,
    enable_usage_metrics=True,
)
```

`allow_interruptions` is not overridden, so it uses Pipecat's framework default (interruptions enabled, unconditional). VAD is stock Silero with `stop_secs=0.4` and no confidence/duration gating:

```1_1:pipeline.py
SileroVADAnalyzer(params=VADParams(stop_secs=0.4))
```

**There is no backchannel/interruption/correction/new-question/stop-command classifier anywhere in the live Pipecat path.** Any detected user speech during `AGENT_SPEAKING` triggers Pipecat's built-in `UserStartedSpeakingFrame` handling, which stops/cancels the bot's TTS unconditionally. This confirms the user's stated hypothesis as a real, live bug, not speculation.

Interesting existing asset: `backend/app/services/voice_turn_taking.py` already implements a materially more sophisticated model — `FloorHolder` (NONE/USER/AGENT/OVERLAP), sustained-floor windows by `TurnSensitivity` (350/650/1100 ms), and an explicit `AGENT_ACK_MAX_MS = 900` concept that already treats brief agent acknowledgments as non-floor-stealing overlap (the mirror image of the backchannel problem, but for agent-side "mm-hm"). **This module is wired into the older PSTN/text-adjacent voice path** (`voice.py`, `pstn_voice_bridge.py`, `voice_session_service.py`) — **not into the live Pipecat WS pipeline** that actually serves gravitre.app today. It is not currently reused by Phase 1 of the new prompt's classifier requirement, but is a legitimate starting point/precedent rather than building from zero.

**Q2 — Current real turn-taking states vs. the proposed 10-state set (USER_SPEAKING, USER_PAUSING, USER_PROBABLY_FINISHED, USER_FINISHED, AGENT_THINKING, AGENT_SPEAKING, USER_INTERRUPTING, AGENT_INTERRUPTED, TOOL_RUNNING, TOOL_COMPLETE):**

None of these 10 states exist as named, distinct states in the live Pipecat path. The live path relies entirely on Pipecat framework primitives (VAD start/stop frames, default interruption handling) with no Gravitre-authored state machine layered on top. The closest real analogue, `voice_turn_taking.py`'s `TurnTakingState`/`FloorHolder`, is a 4-value floor model (NONE/USER/AGENT/OVERLAP) on a *different, non-live* code path — it does not map 1:1 to the proposed 10-state set and is not currently exercised by production voice traffic.

## Why I am stopping here instead of proceeding to Phase 1–6

The prompt itself states the reason precisely: building backchannel classification, progressive narration, and honest tool-state speech mapping on top of a pipeline currently taking 7–18 seconds to produce a first word would make it impossible to attribute a newly-observed problem to the right layer. That condition is confirmed true right now, with fresh evidence, not stale evidence. Proceeding would violate the prompt's own explicit ordering requirement.

## What is required before Phase 1 can start

1. **Human verification** of the current (post text-corruption/jargon-leak fix) state: hard-refresh `gravitre.app`, run the `/ai`, Agent 1, Agent 2 tests from the prior gate, and return `HUMAN_VOICE_CONFIRM 2026-09-04` in the specified format.
2. **Root-cause and fix the 7–18 s first-word latency.** Concretely: instrument (or re-instrument, since the current `data-intelligence` log line does not resolve it) the gap between the routing decision (`pre_llm_ms≈3.5s`, cognitive stages summing to ~1.6s) and `first_text_delta_ms` (12.3–14.9s) to find the ~8–13s of currently-unattributed time. This is very likely a serialized/retried network call or queuing behavior inside `execute_task_streaming`, not a Pipecat/STT/TTS issue (both of those are independently confirmed fast).
3. Re-run the live probe against the fix and confirm P95 is materially closer to a real-time conversational bar before re-attempting human verification.

Only after both close should Phase 1 (backchannel/interruption classifier) begin.
