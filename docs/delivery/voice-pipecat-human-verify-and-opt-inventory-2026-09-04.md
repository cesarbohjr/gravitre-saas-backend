# Voice Pipecat — human verify gate + Part 2 opt inventory (2026-09-04)

**Standing ledger:** Class A (one layer too low), Class B (broken instrument), Class C (silence ≠ health), organic-vs-probe honesty.

---

## PART 1 — Real deployed state (probe-derived; NOT human-closed)

### Deployed tips (checked 2026-09-04)

| Layer | Tip | Evidence |
|-------|-----|----------|
| API (Railway) | `8ac01d95e09b9462f1facd856168da07f8e05cde` | `GET https://api.gravitre.app/health` → `git_sha` |
| Web (Vercel prod) | `6b98dbe6c03abdc898af0b584251887693d3231d` | Deployment `dpl_FrL6DUcFx1RA4QyCwvDDSoa9enNi` **READY**, alias `gravitre.app` |
| Flag | `VOICE_PIPECAT_ENABLED=true` | Status probe: `pipecat_enabled=true`, `default_orchestration=pipecat` |

### What the product path is (when flag on)

1. Browser mic → PCM frames → `wss://api.gravitre.app/api/voice/pipecat/ws`
2. Server Deepgram STT (**Pipecat library default `nova-3-general`** — Gravitre does **not** pass `DEEPGRAM_STT_MODEL` into `DeepgramSTTService`)
3. `GravitreCognitiveLLMService` → `execute_task_streaming(spoken_mode=True)` → **CognitiveTurnKernel**
4. ElevenLabs TTS **`eleven_flash_v2_5`** over **WebSocket** (Pipecat `ElevenLabsTTSService`)
5. JSON PCM audio + `assistant_text` / `transcript` back to FE

HTTP duplex (browser Deepgram **`nova-2`** + `POST /api/voice/session/turn`) remains fallback / e2e `forceHttpDuplex`.

### Probe-derived only (does NOT close Part 1)

| Probe | Verdict | Pointer |
|-------|---------|---------|
| Pipecat WS + governance | **PASS** (API text-ingress smoke) | `docs/delivery/voice-pipecat-phase1-live.json` — tip `8ac01d95`, `CognitiveTurnKernel`, `nl_yes_same_path_as_text`, `orchestration_honesty=PASS` |
| HTTP duplex regression | **PASS** (API) | `docs/delivery/voice-duplex-one-brain-live.json` |
| Human hear / barge-in on `/ai` + agents | **NOT RUN** | Cesar confirmation required |

**Part 1 status: OPEN.** Internal PASS ≠ voice fixed for users (Class A + Class C).

---

## Cesar — step-by-step live verification (required)

Do this on **production** (`https://gravitre.app`), hard-refresh (Ctrl+Shift+R), signed in as you. Use speakers/headphones unmuted. If the orb shows **Enable sound**, tap it (autoplay gate — Class C trap).

### A. Confirm Pipecat path is actually used (instrument cross-check — Class B)

1. Open DevTools → **Network** → filter `pipecat` (or `WS`).
2. Open `/ai` → tap **Talk**.
3. You **must** see a WebSocket to `/api/voice/pipecat/ws` (not only Deepgram browser WS + `/api/voice/session/turn`).
4. If you only see Deepgram mint + `session/turn`, stop and report — FE is not on Pipecat.

### B. Main chat (`/ai`) — audible + latency + barge-in

| # | Do | Pass if | Fail if |
|---|----|---------|---------|
| B1 | Say: “In one short sentence, what is two plus two?” | You **hear** a spoken reply; transcript appears | Silence, orb stuck, text-only, or “Enable sound” ignored |
| B2 | Note wall-clock from end of your speech → first audible syllable (phone stopwatch OK) | Record the number honestly | Guessing / using API smoke numbers as substitute |
| B3 | Ask a second short follow-up in the **same** Talk session | Continuation makes sense | Session dies / wrong context |
| B4 | While the agent is still speaking, interrupt with “Stop — actually tell me the weather instead” | Speech cuts; new turn starts | Agent talks over you with no cut |

### C. Department agent 1

1. Go to `/agents` → open any **Sales** (or Marketing) agent → **Chat** (`/agents/{id}/chat`).
2. Talk → same B1–B4.
3. Confirm WS is still `/api/voice/pipecat/ws`.

### D. Department agent 2 (different department)

1. Open a **Support** or **Finance** agent chat (must be a **different** agent than C).
2. Repeat B1–B4.

### E. Write-governance organic check (optional but valuable)

On `/ai` Talk: “Email Sarah that the campaign moved to Monday.”  
Pass: spoken ask for missing info / confirm — **not** silent send.  
Probe already PASS on text-ingress; this is the organic layer.

### F. Reply format (closes Part 1 only if you send this)

Reply in chat with exactly:

```
HUMAN_VOICE_CONFIRM 2026-09-04
/ai: hear=YES|NO barge=YES|NO wall_ms≈___ pipecat_ws=YES|NO
agent1=<name/dept>: hear=YES|NO barge=YES|NO
agent2=<name/dept>: hear=YES|NO barge=YES|NO
notes: <anything broken>
```

Until that message exists from Cesar, **do not** mark voice fixed and **do not** start Part 2 apply.

## UI 2.0 FINAL — HUMAN_VOICE_CONFIRM waived (2026-09-04)

**Authorization:** Cesar — bypass `HUMAN_VOICE_CONFIRM` for UI 2.0 master program closure; a **separate project** owns human hear/barge-in.

| Claim | Status |
|-------|--------|
| UI 2.0 Voice visual pilot FINAL (for reskin program) | **CLOSED — human confirm WAIVED** |
| Voice functional / human-proven audio | **Still OPEN** — tracked outside UI 2.0 |
| Product copy may claim human-verified Talk audio | **No** |

See `docs/delivery/ui-2-0-final-closure-2026-09-04.md`.

---

## PART 2 — Technique inventory (APPLIED — see closure doc)

**Superseded by:** `docs/delivery/voice-pipecat-part2-flux-opts-2026-09-04.md` + `docs/delivery/voice-pipecat-interrupt-warmup-mutation-2026-09-05.md`.

Cesar authorized apply (`I confirm proceed to Part 2`). Historical inventory below is the pre-apply snapshot at tip `8ac01d95` / FE `6b98dbe6` — do not treat as current live status.

### 2.1 Deepgram Flux + Speak v2 barge-in

| Item | Status | Reasoning |
|------|--------|-----------|
| Current Pipecat STT | **`nova-3-general`** (library default) | `pipeline.py` constructs `DeepgramSTTService(api_key=…)` with no model override |
| Browser/HTTP STT | **`nova-2`** (config default) | `DEEPGRAM_STT_MODEL` / `deepgram_live_ws_url` |
| Flux (`flux-general-en` / `DeepgramFluxSTTService`) | **ABSENT** | No Flux imports; worth evaluating **after** human confirm — would replace Silero/custom turn-taking surface |
| Speak v2 `sendInterrupt` / `SpeakV2SpeechInterrupted` | **N/A today** | Live TTS is **ElevenLabs**, not Deepgram Speak. Flux STT barge-in ≠ Speak v2 TTS interrupt primitives |

**Apply recommendation (post-confirm):** migrate Pipecat STT to `DeepgramFluxSTTService` (`flux-general-en`), drop redundant VAD turn machine where Flux owns EOT; keep CognitiveTurnKernel + write gate unchanged.

### 2.2 ElevenLabs Flash v2.5

| Item | Status | Evidence |
|------|--------|----------|
| Live model | **`eleven_flash_v2_5`** | Config default + Pipecat pipeline + HTTP session; live metrics showed `eleven_flash_v2_5` in phase1 JSON |
| Not v3 / Multilingual v2 on live path | **Confirmed in code** | No v3 model string on voice path |
| Pipecat → ElevenLabs transport | **WebSocket** | Pipecat `ElevenLabsTTSService` (`wss://api.elevenlabs.io`) |
| HTTP duplex TTS | **HTTP stream** (not WS) | `synthesize_speech_stream` POST — fallback path only |
| Concurrency limits on active plan | **NOT RUN / INCONCLUSIVE** | No ElevenLabs subscription/concurrency probe in this session — report from dashboard before claiming capacity |

### 2.3 Pipecat latency techniques

| # | Technique | Status | Notes |
|---|-----------|--------|-------|
| 1 | Interim STT → speculative work | **PARTIAL** | `SpeculativePrefetchProcessor` warms dialogue/sentiment only — **not** full reasoning / tool prefetch |
| 2 | Partial LLM tokens → TTS | **PRESENT (architected)** | Cognitive streams `LLMTextFrame` into ElevenLabs; **organic TTFA** still needs Cesar/stopwatch + tip re-measure |
| 3 | Prompt-prefix caching on voice | **PARTIAL** | Inherited unified-turn provider cache (`cached_prompt_tokens`); no voice-specific prefix warmer |
| 4 | TTS session warm-up / prebuffer | **ABSENT** | No long-lived ElevenLabs warm opener |
| 5 | Speculative tool/retrieval on partials | **ABSENT** (warm-only) | Correct that writes must never speculative-execute; READ prefetch not built yet |
| 6 | Smaller/faster models for short spoken turns | **PRESENT** | `spoken_mode` + `mode="fast"` + conversational depth / task tier on same kernel |

### 2.4 Multi-provider STT fallback

| Item | Status |
|------|--------|
| Deepgram-only duplex/Pipecat | **ABSENT** fallback |
| Research-lookup pattern (Serper→Tavily) | Exists elsewhere; **not** wired to voice STT |
| Apply (post-confirm) | Add primary+fallback with visible fallback log + golden-signals, same pattern as research lookups — e.g. Deepgram primary, second STT vendor on failure/spike |

### 2.5 Live latency re-measure

**RUN on tip `6d6d6d56`** — numbers and honesty caveats in `voice-pipecat-part2-flux-opts-2026-09-04.md` §2.5 (HTTP instrument + Pipecat synth-PCM infra floor). Still miss 700–900ms feel; organic Cesar stopwatch still OPEN.

Mutation flux↔nova3: **LIVE PASS** then restored (`voice-pipecat-interrupt-warmup-mutation-2026-09-05.md`).

---

## What shipped historically in the inventory commit

- This gate + inventory doc (pre-apply snapshot)
- Smoke gate: `orchestration_honesty` when flag on

**Current live Part 2 status:** see Part 2 closure + interrupt/warmup docs (not this snapshot).
