# Phase 0 — Voice bugs root-cause (Pipecat decision gate)

**Date:** 2026-09-04  
**Live tip at diagnosis:** `4554d352f3c304ba45016a052f052931384f6c8c`  
**Artifacts:** `voice-duplex-one-brain-live.json`, `voice-latency-phases-live.json`, `voice-latency-cold-path-breakdown-live.json`

## Explicit recommendation

**(c) Mix — narrow fixes now; Pipecat migration NOT warranted for the current silent-audio / hard failure.**

| Question | Finding |
|----------|---------|
| Is orchestration custom? | **Yes.** Zero Pipecat/LiveKit/Daily deps. Custom: Deepgram WS → `voice_turn_taking` → `POST /api/voice/session/turn` → CognitiveTurnKernel → ElevenLabs stream → FE `HTMLAudioElement` queue. |
| Missing audible audio — point of failure | **TTS request rejected before any audio bytes.** Events reach `voice.ttft` + `voice.agent_speech.start`, then `voice.error`. |
| Confirmed error | ElevenLabs **403 `invalid_output_format`**: bare `output_format=mpeg` is no longer accepted. Allowed enums include `mp3_44100_128`, `ulaw_8000`, etc. |
| Class | **Class A** — fix the shared helper (`normalize_elevenlabs_output_format` in `tier1_voice_service.py`), not call sites. Class C: “agent speech started” ≠ “audio played.” |
| Synchronous Knowledge Fabric blocking? | **No on simple spoken turns.** `reasoning_depth=conversational` skips KNOWLEDGE (`fabric_count=0`). RECALL still runs (~150–220ms). PLAN stage dominates cognitive (~0.7–1.0s). Historical cold TTFT ~5.4s was pre-ACT classify/enrich, not Fabric. Speculative STT-on-interim already exists on FE. |
| Custom barge-in | Live barge-in cancel **PASS** on tip `4554d352`. |

### Why not Pipecat for this failure

Pipecat would not change the ElevenLabs `output_format` query string Gravitre sends. Migrating the orchestration layer to chase silent audio would be the “exciting solution” when the real break is a one-line API enum mismatch in the shared TTS helper.

### Latency (honest, separate)

| Probe class | Cognitive stage sum (pre-TTS) | TTFA |
|-------------|------------------------------:|-----:|
| warm / simple conversational (this tip, TTS broken) | ~1000–1170 ms | null (TTS 403) |
| Historical cold conversational (2026-08-14) | TTFT ~5440 ms | TTFA ~5637 ms |

After the format fix lands, re-measure TTFT/TTFA against the Aug 14 baseline. Further latency work (if still needed) is **pre-ACT / PLAN shrinkage on spoken conversational turns**, not an orchestration-framework swap. A later, separately justified Pipecat case would need evidence that turn-taking/barge-in/media transport—not TTS format or pre-ACT—is the residual pain.

### Orb / surfaces

Main `/ai` and department `agents/[id]/chat` both wire `useVoiceDuplexSession` + `VoiceOrbTakeover` via shared composer. Orb divergence is a presentation/parity check after audio is restored — not a reason to migrate orchestration.

## Fix shipped with this Phase 0 close-out

Shared helper maps legacy `mpeg` → `mp3_44100_128`; stream + batch TTS use the enum; session default updated. Unit tests assert bare `mpeg` never reaches the URL.

**Shipped:** commit `56dbc87bae37f855cbd42ae13e738afeeff25e2d` on `main`  
**Live health:** `git_sha=56dbc87bae37f855cbd42ae13e738afeeff25e2d`

### Post-deploy verification (API probes)

| Probe | Verdict | Evidence |
|-------|---------|----------|
| Duplex one-brain | **PASS** | `voice-duplex-one-brain-live.json` — continuation turn had `voice.ttfa` + 40 `voice.audio.delta`; barge-in + write-governance PASS |
| Latency phases | **PARTIAL** | Audio restored (all probes `ok` with TTFA). Gate `ttft_improved_vs_4632` still FAIL — simple conversational TTFT **13339 ms** / TTFA **13511 ms** (warm TTFT 4454 / TTFA 5674). Latency is a separate follow-up, not a Pipecat justification for silence. |

## Human verification (Cesar) — required before “voice fixed” closure

Do **not** close on API probes alone (program Class C / voice history).

1. On a billed org with voice enabled, open **main chat** `/ai` → Voice → Talk.  
2. Ask one short uncached question. Confirm **you hear** the reply (not just orb motion).  
3. Mid-reply say “wait, only show enterprise opportunities” — confirm barge-in stops playback and re-answers.  
4. Repeat on **two department agent** chats.  
5. Note felt latency vs prior (~4–5s cold); simple turns may still feel slow (API saw ~13s TTFT on one probe).  

Only Cesar’s direct confirmation closes the human gate.

## Phase 1 (Pipecat)

**NOT STARTED** — Phase 0 recommendation does not authorize orchestration migration for the current bugs.

## Latency re-measure (2026-09-04, tip `0205c202`)

Post `fix(voice): skip knowledge + cold classify on spoken conversational turns` deploy. Health `git_sha=0205c2020941d22241a3fdd2139984ab60aea97b` @ `2026-09-04T09:08:37Z`.

| Probe | TTFT ms | TTFA ms | depth | KNOWLEDGE ms | Evidence |
|-------|--------:|--------:|-------|-------------:|----------|
| simple_conversational | 3330 | 3514 | conversational | 0.0 | turn `2776155f-5711-4929-aac7-13de1ee2a185` |
| warm | 3337 | 3536 | conversational | 0.0 | turn `02233353-36bc-43ac-aba8-33a259611cff` |
| consequential_write_shaped | 5361 | 5544 | full | 474.5 | turn `2b7bda60-ea13-42d8-a213-08966d087e8f` |

- Delta vs user baseline (simple): TTFT **-1302** ms (3330 vs 4632); TTFA **-1299** ms (3514 vs 4813). Gate `ttft_improved_vs_4632` **PASS**.
- Latency artifact verdict **PASS** — `docs/delivery/voice-latency-phases-live.json` `generated_at=2026-09-04T09:08:54.311350+00:00`.
- Duplex one-brain **PASS** (barge-in, continuation, write governance, cognitive kernel) — tip `0205c202`; `docs/delivery/voice-duplex-one-brain-live.json`.
- Note: `simple_conversational_turn2` hit `UnboundLocalError: chat_facade` (service_failure); overall latency verdict still PASS on primary simple/write gates.

## Phase 1 (Pipecat) — STARTED 2026-09-04

User authorized move to Phase 1 after Phase 0 narrow fixes. Flag-gated; default duplex remains `POST /api/voice/session/turn`.

| Piece | Location |
|-------|----------|
| Deps | `backend/requirements-extras-voice.txt` → `pipecat-ai[deepgram,elevenlabs,websocket]`; Dockerfile copies extras-voice |
| Flag | `VOICE_PIPECAT_ENABLED` / `voice_pipecat_enabled` (default **false**) |
| Cognitive bridge | `GravitreCognitiveLLMService` → `execute_task_streaming(spoken_mode=True)` |
| Speculative | `SpeculativePrefetchProcessor` on `InterimTranscriptionFrame` |
| WS | `WS /api/voice/pipecat/ws` — JSON/PCM serializer; text ingress for smokes; `{"type":"interrupt"}` barge-in |
| Status | `/api/voice/status` exposes `pipecat_enabled`, `pipecat_ws_path`, `default_orchestration` |
| Live smoke | `scripts/verify-voice-pipecat-phase1-live.py` → `docs/delivery/voice-pipecat-phase1-live.json` |

**Not done until live tip evidence:** Railway install of extras-voice, flag-off duplex regression, flag-on WS `session.ready` + audio, write-governance through Pipecat path. FE still uses HTTP duplex by default.

