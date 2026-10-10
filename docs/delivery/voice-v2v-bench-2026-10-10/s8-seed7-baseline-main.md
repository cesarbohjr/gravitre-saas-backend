# Voice scenario bench: base-s8-seed7

Runs per scenario: 20 · seed base: 7 · git: b7c93f4a · wall time: 6.9 s · settings overrides: none

Times are milliseconds, shown as P50 / P95 (n = runs where the event happened). "played" is the modelled browser speaker; "sent" is arrival at the client socket. First-audio and completion are measured from the user's acoustic end of speech of the measured request.

## Latency

| Scenario | first audio (any) | first filler/progress | first answer (played) | first answer (sent) | task completion |
|---|---|---|---|---|---|
| S8 approval "yes... wait" | 1883 / 7128 (n=20) | – | 1883 / 7128 (n=20) | 1763 / 6948 (n=20) | 1544 / 2169 (n=20) |

## Interruption, correctness and speculation

| Scenario | barge-in → last old frame sent | barge-in → silence (played) | late old frames recv / played | mis-stamped frames | premature response | premature actions | history = heard | brain s after interrupt (orphan runs) | spec started / adopted / wasted s | outcome |
|---|---|---|---|---|---|---|---|---|---|---|
| S8 | – | – | – | 260 | 0/20 | 5 | 0/20 | 0.0 (0) | 20 / 20 / 0.0 | no_send_attempted 15, email_sent 5 |

## Scenario conditions

- **S8 approval "yes... wait"**: Bot drafts an email and asks to send; user says "yes", pauses ~0.5 s, says "wait". Flux may commit "yes" on the pause. Expected: No email is sent (the final intent is "wait"). Conditions: brain_first_token_s=0.9, token_s=0.035, tts_first_byte_s=0.25, tts_generation_speed=3.0, tts_word_audio_s=0.32, late_audio_s=0.0, user_word_s=0.3, stt_start_detect_s=0.15, stt_eager_delay_s=0.2, stt_eot_delay_s=0.45, browser_lead_s=0.12, network_s=0.0, jitter=0.25, stt_interims=False.

## What the harness models, and what it does not

- Real: every Pipecat processor between the socket and the providers, exactly as build_pipecat_voice_task wires it (utterance gate, transcript relay, speculative prefetch/generation, Flux turn strategies incl. backchannel grace window, Cognitive LLM bridge with deep ack and tool narration, interrupt reporter with stop marker and played-audio reconciliation, Pipecat TTS audio contexts and word timestamps, websocket output pacing, spoken-text tap, durable persistence and the barge-in write gate).
- Scripted STT follows Pipecat 1.12 Deepgram Flux frame semantics: StartOfTurn, EagerEndOfTurn/TurnResumed, EndOfTurn with finalized transcript. Flux 1.12 pushes no interim transcripts, so none are sent (as in production). Flux's own end-of-turn decision is a fixed, jittered delay after speech ends, not a model of its confidence.
- Fake TTS is shaped like the ElevenLabs websocket service (one context per reply, first-byte delay, faster-than-real-time streaming, flush/close). Audio is a constant tone whose sample value encodes the segment, so labels survive re-chunking. Provider-side late frames are modelled; ElevenLabs alignment quirks are not.
- Brain is scripted (first-token delay, streamed tokens, tool calls, failures, governed writes checked with the real raise_if_barge_in_blocks_invoke). It does not model the real CognitiveTurnKernel, model routing or tool selection; the plans are fixed per scenario.
- Browser model reproduces use-voice-duplex-session.ts drop rules (reply_id <= interrupted id, flush on speech.interrupted) and the voice-pcm-jitter.ts lead (120 ms initial, +60 ms per mid-reply underrun, max 320 ms). It does not model the client-side bargeIn() path (the server does not relay interim transcripts), the HTTP fallback watchdog, or AudioContext scheduling jitter.
- NOT modelled: acoustics, microphone echo and echo cancellation, real Deepgram/ElevenLabs/model latency distributions, network latency/jitter/loss (network_s=0), CPU load (virtual time makes processing free), multi-worker Redis stop markers (in-process fallback), and the read-only prefetch services (counted, not run).
- Virtual clock: asyncio timers and time.time/monotonic/perf_counter are virtual; worker threads take zero virtual time. Results are deterministic for a given seed and code version.
