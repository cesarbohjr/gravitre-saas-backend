# Voice Pipecat Part 2 — Flux + latency opts (2026-09-04/05)

Cesar authorized Part 2 apply (`I confirm proceed to Part 2`). Follow-ups (interrupt / warm-up / READ prefetch / STT mutation) applied separately — see `voice-pipecat-interrupt-warmup-mutation-2026-09-05.md`.

**Standing ledger:** Class A / B / C; probe PASS ≠ organic hear closed.

## Shipped (code) — live tip `6d6d6d56` (API health 2026-09-05)

| Item | Action | Notes |
|------|--------|-------|
| 2.1 Flux STT | **ADDED + LIVE** | `DeepgramFluxSTTService` / `flux-general-en`; native EOT; Silero VAD omitted when Flux |
| Speak v2 barge-in | **N/A** (TTS=ElevenLabs) | **Equivalent LIVE:** `speech.interrupted` + FE `playback_offset_ms` |
| 2.2 Flash v2.5 + WS | **CONFIRMED LIVE** | `tts_model=eleven_flash_v2_5`, `tts_transport=websocket` |
| ElevenLabs concurrency | **REPORTED (dashboard)** | Cesar 2026-09-04: **8,264 / 90,000** credits; Concurrent Requests **max used = 2** (observed peak, not a claimed plan ceiling) |
| 2.3.1 Interim → speculative | **EXTENDED** | READ-only query-embed + knowledge + tool-doc warm; cancel on partial change; `write_exec=false` |
| 2.3.2 Partial LLM → TTS | **ALREADY PRESENT** | Cognitive stream → ElevenLabs |
| 2.3.3 Prefix cache | **ALREADY PRESENT** (inherited) | No second cache |
| 2.3.4 TTS warm-up | **ADDED + LIVE** | Silent ElevenLabs WS preconnect → `tts.warmed` / `tts_warmup=elevenlabs_ws_preconnect` |
| 2.3.5 Speculative tools | **READ warm only** | Never executes writes/tools |
| 2.3.6 Complexity tiering | **ALREADY PRESENT** | `spoken_mode` + fast path |
| 2.4 STT fallback | **ADDED** | Primary Flux → fallback Nova-3; visible `voice_stt_fallback_to_*` + WS `stt_fallback` |
| Live flux↔nova3 mutation | **LIVE PASS** then restored | See interrupt/warmup/mutation doc |

### Config levers

- `VOICE_PIPECAT_STT` = `flux` \| `nova3` \| `openai` (Railway currently **`flux`**)
- `VOICE_PIPECAT_STT_FALLBACK_ENABLED` / `VOICE_PIPECAT_STT_FALLBACK`
- `VOICE_PIPECAT_FLUX_EAGER_EOT` / `VOICE_PIPECAT_FLUX_EOT`

## Live evidence (tip `6d6d6d5672dc81ceec7798a1d3fd2625b2821e48`)

| Probe | Verdict | Evidence |
|-------|---------|----------|
| Pipecat + Flux honesty | **PASS** | `voice-pipecat-phase1-live.json` — `stt_provider=deepgram_flux`, `stt_model=flux-general-en`, `tts_model=eleven_flash_v2_5`, `tts_transport=websocket`, warm-up events present |
| HTTP duplex regression | **PASS** | `voice-duplex-one-brain-live.json` |
| Latency phases (HTTP `session/turn` — **not** FE mic) | **PASS** (gates) | `voice-latency-phases-live.json` @ `2026-09-05T04:33:16Z` |
| Pipecat E2E TTFA (synth PCM → live WS — **infra floor**, not Cesar hear) | **RUN** / miss 500ms bar | `voice-pipecat-live-latency-2026-09-04.json` |
| Mutation flux↔nova3 | **LIVE PASS** | nova3 forced → restore flux; documented in interrupt/warmup doc |
| ElevenLabs concurrency | **REPORTED** | Dashboard: 8,264/90,000 credits; concurrent max used 2 |

### 2.5 Latency re-measure (do not average instruments)

#### A. HTTP duplex instrument (`session/turn`)

| Scenario | TTFT ms | TTFA ms | vs baseline 4632/4813 | vs 700–900 target |
|----------|--------:|--------:|----------------------:|-------------------|
| User-stated pre-opt baseline | 4632 | 4813 | — | miss |
| **This tip `warm`** | 3174 | 3362 | improved | miss |
| **This tip `simple_conversational`** | 2203 | 2457 | TTFT −2429 / TTFA −2356; gate `ttft_improved_vs_4632=PASS` | miss |
| **This tip `simple_conversational_turn2`** | 7063 | 9147 | worse | miss |
| **This tip `consequential_write_shaped`** | 4627 | 4843 | ~flat | miss |

#### B. Pipecat WS infra floor (synth speech → production `/api/voice/pipecat/ws`)

| Scenario | E2E TTFA p50 ms | E2E TTFA p95 ms | TTS-only TTFA p50 | sub_500ms_p95 |
|----------|---------------:|---------------:|------------------:|---------------|
| `simple_conversational` (n=5) | 5844 | 7951 | ~172 | **false** |
| `consequential_write_shaped` (n=3) | 12498 | 13805 | — | **false** |

Honest read: Flux + Flash WS + warm-up + READ prefetch are live on Pipecat. **TTS chunk latency is sub-200ms**, but **end-to-end (STT + Cognitive + TTS) remains multi-second** on both instruments — far from 700–900ms feel. Class B: neither instrument is Cesar's organic stopwatch on `/ai`.

## Organic /ai hear + barge-in (2026-09-05 follow-up)

| Check | Verdict | Evidence |
|-------|---------|----------|
| Browser open `https://gravitre.app/ai` | **BLOCKED — login required** | Redirected to `/login` (no Cesar session in automation browser) |
| Probe-derived Pipecat path (text/synth) | **PASS** (not organic hear) | `voice-pipecat-phase1-live.json` / latency JSON — Class A: not a substitute for Cesar hear |
| HUMAN_VOICE_CONFIRM from Cesar | **STILL OPEN** | Cannot close from agent without signed-in mic session |

**Honest:** Organic hear/barge-in is **not closed** until Cesar (or a signed-in human session) posts the confirm block. Automation cannot complete microphone hearing.

## Remaining

1. Organic Cesar hear / barge-in on Pipecat+Flux (still OPEN outside UI 2.0 waiver).
2. Further latency cutover if 700–900ms remains binding (cognitive / pre_act dominate; TTS is not the bottleneck on Pipecat floor).
3. ~~ElevenLabs concurrency~~ — dashboard reported (credits + max used 2); still confirm plan **ceiling** if multi-session load is planned.
