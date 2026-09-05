# Root-cause dig: the ~8–13s unattributed voice-latency gap

**Date:** 2026-09-04/05
**Deployed tip:** `23a3773877917315b1ba06f86d85aff7255c8f0b` (instrumentation-only, log lines added, zero behavior change, 110/110 `unified_turn` tests pass)
**Follow-up to:** `docs/delivery/voice-conversational-realism-preflight-2026-09-04.md` (pre-flight FAILED — this doc digs into *why*)

## Method

Added two new log lines that expose numbers the code already computed but never logged:
1. `unified_turn_shadow_breakdown` — logs `registry_tools_ms`, `narrow_tools_ms`, `context_prompt_ms`, `pre_model_ms`, `openai_create_schedule_ms`, `model_ttft_ms`, `wall_to_first_token_ms`, `progressive_round_ms`, token counts, on every unified-turn model call.
2. `apply_unified_turn_live_guards_ms` — timing for the three pre-checks (channel override, meta-capability, pending-reply) that run before the main model call.

Then re-ran the live probe (`scripts/measure-voice-pipecat-live-latency.py`) against production and cross-referenced the new log lines with existing Pipecat/Deepgram DEBUG logs (`railway logs`) for the same time window.

## Result: the "unattributed gap" is now attributed — it was never in the final model call

**What is fast (confirmed, not the bottleneck):**

| Stage | Measured (live, this run) |
|---|---|
| `apply_unified_turn_live` guard checks (channel/meta/pending) | **0 ms**, every turn |
| `registry_tools_ms` / `narrow_tools_ms` / `context_prompt_ms` | 0–110 ms |
| Final answer-generation model call (`model_ttft_ms`) | 365 ms – 2,945 ms, median ~600–700 ms |
| `wall_to_first_token_ms` (full unified-turn call, incl. any progressive round) | 477 ms – 3,593 ms |
| TTS (`tts_ttfa_ms`, from the probe) | 150 ms – 1,430 ms |

None of this sums to 7–18 seconds. The previous instrumentation (the `data-intelligence` SSE log) was measuring elapsed time inside `cognitive_llm.py` from *its own* `turn_start`, which begins only after Pipecat has already finished STT + turn-detection — so the gap was never inside the reasoning/model layer at all. It's upstream.

## Two real, confirmed contributors found instead

### 1. Sequential LLM calls stacked before the final answer (structural, Class B)

`agent_intelligence.execute_task_streaming` calls these **in sequence, awaited, before `CognitiveTurnKernel.run_pre_act`**:
- `contextual_understanding_service.understand()` — for any message over 8 words where rule-based goal inference doesn't resolve, this makes **its own separate LLM completion call** (`get_model_router().complete(...)`, `contextual_understanding_service.py:71-76`). "Email Sarah that the campaign moved to Monday." (8 words) and any real multi-clause voice request trigger this.
- `task_classifier.classify()`
- `persona_service.get_persona_for_request()`
- Then `CognitiveTurnKernel.run_pre_act` itself, whose `PLAN` stage alone measured **1,204–1,450 ms** live (confirmed via the `cognitiveStageMs` breakdown already being logged).
- Then, *after all of that*, the actual answer-generation model call (365 ms – 2,945 ms measured above).

That is up to **three separate, sequential LLM round-trips per voice turn** (contextual understanding → CognitiveTurnKernel PLAN → final answer), none of them parallelized, none of them cached against each other. This is consistent with why `consequential_write_shaped` (longer, multi-clause utterances) measured far worse (P50 15.1s / P95 20.1s) than `simple_conversational` (P50 8.6s / P95 9.8s) — longer/more complex messages are more likely to trigger the extra `contextual_understanding` LLM call and additional progressive tool-disclosure rounds (one run showed `progressive_round_ms=[630, 2950]`, i.e. two full model round-trips in one turn).

### 2. Deepgram Flux end-of-turn detection + watchdog-triggered silence injection (confirmed live, dominant contributor)

Direct Pipecat DEBUG logs from this exact probe run, connection `#7` (`simple_conversational`, utterance = "What is two plus two?"):

```
03:08:38.624  Connected to Flux - ready to stream audio
03:08:39.879  User started speaking
03:08:41.333  WARNING  No audio received for 500 ms. Sending silence to Flux to prevent a dangling task
03:08:41.953  WARNING  No audio received for 500 ms. Sending silence to Flux to prevent a dangling task
03:08:43.215  WARNING  No audio received for 500 ms. Sending silence to Flux to prevent a dangling task
03:08:46.219  User stopped speaking
```

**6.3 seconds** elapse between "user started speaking" and "user stopped speaking" for a 2-second utterance, driven by three separate 500ms+ "no audio received" watchdog events that force Flux to keep waiting before it will commit end-of-turn. This is the single largest, directly-observed contributor to the measured end-to-end latency, and it happens **before** any of the reasoning/model work above even starts.

**Important, honest caveat — this is not yet proven to be a real-user bug:** the probe streams synthesized speech from a local machine, over the open internet, into the production WebSocket (`railway run` → `wss://api.gravitre.app`), using fixed 20ms-chunk pacing with `asyncio.sleep` and no jitter buffer. The watchdog gaps could be:
(a) a real characteristic of Flux's end-of-turn behavior under any real-world network jitter (which would also affect real browser users on imperfect connections), or
(b) an artifact specific to this probe script's naive WAN-hop chunk delivery, which a real browser's audio pipeline (MediaRecorder/AudioWorklet, same-origin WebSocket, typically lower jitter) would not reproduce.

This is exactly the kind of question the standing gate requires a **human**, not a probe, to answer — it cannot be resolved by more synthetic-audio measurement.

## Updated latency attribution (simple_conversational, ~8.6s P50)

| Stage | Contribution |
|---|---|
| STT / Flux end-of-turn + watchdog delay | **~6.3s observed** (dominant, confirmed via debug logs) |
| Pre-CognitiveTurnKernel services (contextual understanding, classifier, persona, task state) | not individually timed yet — bounded above by (first CognitiveTurnKernel yield ≈3.5–4s since `cognitive_llm.py` turn_start) minus (CognitiveTurnKernel's own 1.6s) ≈ **1.9–2.4s** |
| CognitiveTurnKernel (RECALL+PLAN) | **~1.6s** (confirmed) |
| Final answer-generation model call | **0.4–3.6s** (confirmed, median ~0.6–0.7s) |
| TTS first byte | **0.15–1.4s** (confirmed) |

These stack roughly to the observed 8–10s for simple turns and, with an extra `contextual_understanding` LLM call plus a second progressive tool-disclosure round, to the observed 15–20s for write-shaped turns.

## What this does *not* do

This is diagnosis only — no latency fix has been applied, and per the standing pre-flight gate (`voice-conversational-realism-preflight-2026-09-04.md`), no conversational-realism (Phase 1–6) work has started. Candidate fixes that would need explicit go-ahead before implementation:
1. Parallelize `contextual_understanding_service.understand()` with `task_classifier.classify()` / persona resolution instead of running them sequentially, or gate the extra LLM call off for `spoken_mode` the same way `tier0_skip` and `reasoning_depth` already special-case voice.
2. Investigate whether Flux's watchdog/end-of-turn behavior reproduces with real browser-mic audio (not just this synthesized-audio probe) — needs either a browser-network trace or Cesar's own human test.
3. Consider whether `unified_turn_stream_timeout_s=20.0` and up-to-2 progressive rounds are appropriate for voice, where every extra round is a second, full sequential model call.
