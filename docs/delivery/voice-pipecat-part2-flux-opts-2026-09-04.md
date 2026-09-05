# Voice Pipecat Part 2 — Flux + latency opts (2026-09-04)

Cesar authorized Part 2 apply after Part 1 confirmation.

## Shipped (code) — tip ancestor `afa8020b`, live tip `23a37738`

| Item | Action | Notes |
|------|--------|-------|
| 2.1 Flux STT | **ADDED + LIVE** | `DeepgramFluxSTTService` / `flux-general-en`; native EOT; Silero VAD omitted when Flux |
| Speak v2 barge-in | **N/A** | TTS remains ElevenLabs; FE still sends `{"type":"interrupt"}` |
| 2.2 Flash v2.5 + WS | **CONFIRMED LIVE** | session.ready `tts_model=eleven_flash_v2_5`, `tts_transport=websocket` |
| ElevenLabs concurrency | see live section | |
| 2.3.1 Interim → speculative | **EXTENDED** | READ-only query-embed warm + dialogue/sentiment; cancel on partial change; `write_exec=false` |
| 2.3.2 Partial LLM → TTS | **ALREADY PRESENT** | Cognitive stream → ElevenLabs |
| 2.3.3 Prefix cache | **ALREADY PRESENT** (inherited) | No second cache |
| 2.3.4 TTS warm-up opener | **NOT ADDED** | `auto_mode=True` only; no silent opener |
| 2.3.5 Speculative tools | **READ embed only** | Never executes writes/tools |
| 2.3.6 Complexity tiering | **ALREADY PRESENT** | `spoken_mode` + fast path |
| 2.4 STT fallback | **ADDED** | Primary Flux → fallback Nova-3; visible `voice_stt_fallback_to_*` + WS `stt_fallback` |

### Config levers

- `VOICE_PIPECAT_STT` = `flux` \| `nova3` \| `openai`
- `VOICE_PIPECAT_STT_FALLBACK_ENABLED` / `VOICE_PIPECAT_STT_FALLBACK`
- `VOICE_PIPECAT_FLUX_EAGER_EOT` / `VOICE_PIPECAT_FLUX_EOT`

## Live evidence (tip `23a3773877917315b1ba06f86d85aff7255c8f0b`)

| Probe | Verdict | Evidence |
|-------|---------|----------|
| Pipecat + Flux honesty | **PASS** | `voice-pipecat-phase1-live.json` — `stt_provider=deepgram_flux`, `stt_model=flux-general-en`, `stt_honesty=PASS`, `tts_model=eleven_flash_v2_5`, `tts_transport=websocket`, governance PASS |
| HTTP duplex regression | **PASS** | `voice-duplex-one-brain-live.json` — barge-in, continuation, write governance, CognitiveTurnKernel |
| Latency phases (HTTP `session/turn` instrument — **not** FE mic/Pipecat organic) | **PASS** (gates) / numbers below | `voice-latency-phases-live.json` @ `2026-09-05T03:08:24Z` |
| Mutation flux↔nova3 | **UNIT PASS** / **LIVE NOT RUN** | Unit: `build_pipecat_stt(override=nova3)` → `DeepgramSTTService` / restore → `DeepgramFluxSTTService`. Live Railway `VOICE_PIPECAT_STT` flip blocked pending explicit var-change approval |
| ElevenLabs concurrency | **INCONCLUSIVE** | API key present on Railway; local/CLI subscription probe returned no usable payload this session — check ElevenLabs dashboard concurrency before claiming capacity |

### Latency vs prior benchmarks (probe-derived HTTP voice path — do not average)

| Scenario | TTFT ms | TTFA ms | vs baseline 4632/4813 | vs 700–900 target |
|----------|--------:|--------:|----------------------:|-------------------|
| User-stated pre-opt baseline | 4632 | 4813 | — | miss |
| Prior post-narrow conversational (`0205c202` doc) | 3330 | 3514 | improved vs baseline | miss |
| **This tip `warm`** | 7805 | 7985 | worse | miss |
| **This tip `simple_conversational`** | 4109 | 4291 | TTFT −523 / TTFA −522 | miss |
| **This tip `simple_conversational_turn2`** | 3856 | 4197 | improved vs baseline | miss |
| **This tip `consequential_write_shaped`** | 9039 | 9238 | slower (full depth) | miss |

Honest read: Flux STT + READ prefetch are live on Pipecat, but **end-to-end HTTP duplex latency instrument still multi-second** — far from 700–900ms feel target. Class B: this instrument is HTTP `session/turn`, not FE mic→Pipecat wall-clock.

## Remaining

1. Live mutation: set `VOICE_PIPECAT_STT=nova3` on Railway → smoke expect `deepgram_nova3` → restore `flux`.
2. Organic Cesar hear on Pipecat+Flux path (separate from probe PASS).
3. Further latency work if target remains binding (model TTFT / pre_act still dominate on HTTP instrument).
