# Voice Pipecat — interrupt report, TTS warm-up, READ prefetch, STT mutation (2026-09-04/05)

## Applied

| Ask | What shipped | Live |
|-----|--------------|------|
| Deepgram Speak v2 interrupt | **N/A for Speak v2** (TTS is ElevenLabs). **Equivalent applied:** `ElevenLabsInterruptReporter` → `speech.interrupted` with `spoken_text` / `full_draft_text` / `playback_offset_ms`; FE sends offset on barge-in | session.ready `speak_v2=false`; events include `speech.interrupted` on tip |
| Silent TTS warm-up | **ADDED** — `warm_elevenlabs_tts_connection` preconnects ElevenLabs WS (no audible opener) | `tts.warmed` event + `tts_warmup=elevenlabs_ws_preconnect` |
| Speculative write/tool exec | **NOT applied (write_exec=false)** — expanded **READ-only**: query embed + knowledge rows + tool-doc catalog warm; write-shaped skips knowledge warm | logs `write_exec=false` |
| Live `VOICE_PIPECAT_STT=nova3` then restore `flux` | **DONE** | below |

## Mutation proof (live)

| Step | Tip | Expect | Result | Evidence |
|------|-----|--------|--------|----------|
| Force `nova3` | `578d9c03` | `deepgram_nova3` | **PASS** | `stt_honesty=PASS`, `stt_provider=deepgram_nova3` in phase1 JSON (mutation run) |
| Restore `flux` | `54df0d6c` | `deepgram_flux` | **PASS** | `voice-pipecat-phase1-live.json` @ tip `54df0d6c` — `stt_provider=deepgram_flux`, `stt_honesty=PASS`, `tts.warmed` present |

## Tip note

Code for interrupt/warm/READ prefetch landed in `578d9c03` (bundled with latency skip commit). Live restore tip `54df0d6c` includes Flux default after Railway var restore.
