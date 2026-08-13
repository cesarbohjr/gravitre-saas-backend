# Voice × One Brain — Phase 0 reconciliation (2026-08-13)

**Rule:** Report before any Part 2 new build. Labels: EXISTS / PARTIAL / MISSING.  
**Tip at write:** `dcd85baf` (voice chrome) atop `3a5966ff` / `42c66f92` (One Brain).

---

## Executive verdict

Voice **already routes reasoning through CognitiveTurnKernel** when `spoken_mode=True` on `execute_task_streaming` (`surface=voice`). It is **not** a separate intelligence brain. The live UX is still **half-duplex** (push-to-speak → send → batch TTS). Full-duplex, barge-in propagation, AnalyserNode reactivity, and live Deepgram WS remain the Part 2 build surface — not a greenfield voice stack.

---

## Reconciliation table

| # | Capability | Status | Notes |
|---|------------|--------|-------|
| 1 | Deepgram STT + ElevenLabs TTS | **PARTIAL** | Batch STT/TTS live; streaming TTS exists; Deepgram live WS helper unwired |
| 2 | Provisional turn-taking / endpointing | **PARTIAL** | Backend `voice_turn_taking.py` + API; not FE-wired on `/ai` |
| 3 | Text/voice UX + waveform/orb | **PARTIAL** | Shared composer + orb exist; **AnalyserNode gap still open** (keyframes only) |
| 4 | SPOKEN register (Module D) | **EXISTS** | `spoken_register_section` via Module D unified prompt |
| 5 | Write governance parity | **PARTIAL** | Same `awaiting_confirm` / NL yes path as text; live voice-write prove still needed |
| 6 | Latency benchmarks | **PARTIAL** | Targets 700–900ms documented; duplex E2E TTFA not continuously measured |
| 7 | CognitiveTurnKernel path | **EXISTS** | `spoken_mode` → `run_pre_act(surface="voice")` inside streaming chat |
| — | Barge-in / interrupt | **PARTIAL** | UI can stop TTS; no acoustic AEC / cancel-in-flight generation |
| — | Full-duplex | **MISSING** (product) | No simultaneous listen+speak loop |
| — | Provider abstraction | **PARTIAL** | Thin adapters; not multi-provider registry |

---

## Call chain (live chat)

```
FE Speak (MediaRecorder) → POST /api/voice/stt (batch Deepgram)
→ user Send /api/chat { spoken_mode: true }
→ assistant.py → execute_task_streaming(spoken_mode=True)
→ CognitiveTurnKernel.run_pre_act(surface="voice", …)
→ apply_unified_turn_live(…, spoken_mode=True)
→ SSE text → FE → POST /api/voice/tts (batch ElevenLabs)
```

Alternate (built, not FE-wired): `POST /api/voice/session/turn` → same `execute_task_streaming` + streaming TTS chunks.

**Do not rebuild:** STT/TTS providers, SPOKEN register, kernel intake for spoken turns, shared composer/orb chrome.

**Part 2 must add:** FE ↔ live STT + turn-taking → session turn; barge-in cancel; AnalyserNode; shared conversation continuity proof; latency instrumentation; acceptance-scenario recording.

---

## Dependency

Part 2 proceeds only after Part 1 seven items report FULL with live evidence (this program).
