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

## Human verification (Cesar) — required before “voice fixed” closure

Do **not** close on API probes alone (program Class C / voice history).

1. On a billed org with voice enabled, open **main chat** `/ai` → Voice → Talk.  
2. Ask one short uncached question. Confirm **you hear** the reply (not just orb motion).  
3. Mid-reply say “wait, only show enterprise opportunities” — confirm barge-in stops playback and re-answers.  
4. Repeat on **two department agent** chats.  
5. Note felt latency vs prior (~4–5s cold).  

Only Cesar’s direct confirmation closes the human gate.
