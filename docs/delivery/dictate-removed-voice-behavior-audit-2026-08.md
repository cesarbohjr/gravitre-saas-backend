# Dictate removal + Voice behavior audit (2026-08-09)

## Phase 1 — Dictate removed

**Policy:** No separate speech-to-text-only “Dictate” control. Text|Voice is the sole voice entry; Speak mic mounts only when modality is Voice.

| Surface | Change |
|---|---|
| `SharedChatComposerControls` | Speak mic only when `modality === "voice"` |
| `VoiceInputButton` | Relabeled Speak / Listening; Dictate copy gone |
| `/ai`, agent chat, landing | `onVoiceInputError`; no Dictate props |
| Settings voice policy | “Text\|Voice” only |
| Pricing / plans copy | “Voice included (Text \| Voice)” |
| `check-chat-surface-drift.mjs` | Forbids Dictate / standalone VoiceInputButton |

**Kept (shared mechanism, not Dictate-only):** `POST /api/voice/stt`, Deepgram client, `useSpeechRecognition` (used by Voice Speak).

## Phase 2 — Conversational behavior vs industry standard (honest)

Architecture fact on tip: live chat Voice is **modality + push-to-Speak STT into composer + send + spoken_mode + auto-TTS**, not a continuous duplex WebRTC/session loop. Backend provisional turn-taking (`voice_turn_taking.py`) and `stream_voice_turn_events` exist but are **not wired into `/ai` or agent-chat composers**.

| Check | Verdict | Evidence / gap |
|---|---|---|
| Turn-taking (hesitations / um / pauses) | **PARTIAL / not live on chat FE** | Eager/Normal/Patient logic unit-tested in backend; FE still push-to-speak + manual/send — does not stream provisional partials into turn-taking state during chat Voice |
| E2E latency (stop speaking → agent audio starts) | **NOT RUN as continuous session** | Prior honest target ~700–900ms (STT+TTS). Current path adds user Send + full chat turn before TTS — wall-clock will exceed Flash-only first-byte. Measure STT/TTS legs separately if needed; do not claim ChatGPT-class continuous latency |
| Spoken register (Module D) | **BUILT** | `spoken_mode=True` → Register 5 in `module_d_unified_voice_spec.py` / unified turn; FE sends `spoken_mode` when Voice modality active |
| Barge-in | **GAP** | Starting Speak while TTS plays does **not** auto-`stopAgentVoice`; acoustic AEC listed as not-built (`voice_acoustic_signal.other_missing_ml_capabilities_report`). User must hit Stop |
| Self-recognition by name | **BUILT in prompt stack** | Voice agent profile + Module D inject name; live spoken exchange still requires human mic confirm on tip after Vercel READY |

## Closing gaps (named)

1. Wire FE Voice modality to continuous STT partials + `voice_turn_taking` finalize (or `stream_voice_turn_events`) instead of push-to-Speak → textbox → Send.  
2. On Speak-start while `ttsSpeaking`, call `stopAgentVoice()` (minimum barge-in).  
3. Instrument TTFA on the live Voice path and publish real p50/p95 against 700–900ms.  
