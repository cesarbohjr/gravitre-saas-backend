# Voice Pipecat Part 2 — Flux + latency opts (2026-09-04)

Cesar authorized Part 2 apply after Part 1 confirmation.

## Shipped (code)

| Item | Action | Notes |
|------|--------|-------|
| 2.1 Flux STT | **ADDED** | `DeepgramFluxSTTService` / `flux-general-en`; native EOT; Silero VAD omitted when Flux |
| Speak v2 barge-in | **N/A** | TTS remains ElevenLabs; FE still sends `{"type":"interrupt"}` |
| 2.2 Flash v2.5 + WS | **CONFIRMED** | Forced remap off v3/turbo; `auto_mode=True`; status `pipecat_tts` |
| ElevenLabs concurrency | **NOT RUN** until tip + API key probe | Record in live section when available |
| 2.3.1 Interim → speculative | **EXTENDED** | READ-only query-embed warm + dialogue/sentiment; cancel on partial change; `write_exec=false` |
| 2.3.2 Partial LLM → TTS | **ALREADY PRESENT** | Unchanged Cognitive stream → ElevenLabs |
| 2.3.3 Prefix cache | **ALREADY PRESENT** (inherited) | No second cache |
| 2.3.4 TTS warm-up opener | **NOT ADDED** | No clean silent warm without audible artifact; `auto_mode=True` only |
| 2.3.5 Speculative tools | **READ embed only** | Never executes writes/tools |
| 2.3.6 Complexity tiering | **ALREADY PRESENT** | `spoken_mode` + fast path |
| 2.4 STT fallback | **ADDED** | Primary Flux → fallback Nova-3 (OpenAI optional); visible `voice_stt_fallback_to_*` log + WS `stt_fallback` event |

### Config

- `VOICE_PIPECAT_STT` = `flux` \| `nova3` \| `openai` (mutation lever)
- `VOICE_PIPECAT_STT_FALLBACK_ENABLED` (default true)
- `VOICE_PIPECAT_STT_FALLBACK` = `nova3` \| `openai`
- `VOICE_PIPECAT_FLUX_EAGER_EOT` / `VOICE_PIPECAT_FLUX_EOT`

### Mutation proof plan (live)

1. Tip with default `flux` → smoke expects `stt_provider=deepgram_flux` (`VOICE_PIPECAT_STT_EXPECT`).
2. Set Railway `VOICE_PIPECAT_STT=nova3` + redeploy → smoke with `VOICE_PIPECAT_STT_EXPECT=deepgram_nova3` PASS.
3. Restore `flux` → expect `deepgram_flux` again.

## Live evidence (fill after Railway tip)

| Probe | Tip | Verdict | Pointer |
|-------|-----|---------|---------|
| Pipecat phase1 + Flux honesty | _pending_ | | `voice-pipecat-phase1-live.json` |
| HTTP duplex regression | _pending_ | | `voice-duplex-one-brain-live.json` |
| Latency phases (HTTP session/turn instrument) | _pending_ | | `voice-latency-phases-live.json` — probe-derived, not FE mic |
| Mutation flux↔nova3 | _pending_ | | |
| ElevenLabs subscription concurrency | _pending_ | INCONCLUSIVE until probed | |

**Organic FE hear:** still Cesar’s ongoing product bar; this Part 2 is API/orchestration.
