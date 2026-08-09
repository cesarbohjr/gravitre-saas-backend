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
| Barge-in | **PARTIAL** | Minimum: Speak-start while TTS calls `onStop` → `stopAgentVoice` (shared composer). Acoustic AEC / true duplex interrupt still **GAP** (`voice_acoustic_signal.other_missing_ml_capabilities_report`) |
| Self-recognition by name | **BUILT in prompt stack** | Voice agent profile + Module D inject name; live spoken exchange still requires human mic confirm on tip after Vercel READY |

## Closing gaps (named)

1. Wire FE Voice modality to continuous STT partials + `voice_turn_taking` finalize (or `stream_voice_turn_events`) instead of push-to-Speak → textbox → Send.  
2. ~~On Speak-start while `ttsSpeaking`, call `stopAgentVoice()`~~ — shipped as minimum barge-in in shared composer; AEC / acoustic interrupt still open.  
3. Instrument TTFA on the live Voice path and publish real p50/p95 against 700–900ms.  

## Live verification (2026-08-09)

| Check | Result | Evidence |
|---|---|---|
| Git tip (web) | PASS | Vercel production `dpl_BEWvcGdECXgARS3m4TNsxbx1QieX` READY · commit `ffe79feb9d2b102e8e4e66f2df792eb103c4c02c` · aliases include `gravitre.app` (prior Dictate-removal tip `dpl_GYitjhs…` / `c2fe6c70` superseded) |
| API tip | PASS (unchanged; FE-only ship) | `GET https://api.gravitre.app/health` @ 2026-08-09T18:01:58Z → `git_sha=cba337441def633b3782f233edb086901e09366b` |
| Drift CI | PASS | `node scripts/check-chat-surface-drift.mjs` → `chat-surface-drift PASS` (pre-commit on `ffe79feb`) |
| Dictate gone from marketing | PASS | Live `https://gravitre.app/pricing` DOM: `dictateCount=0`; features show `Voice included — Text \| Voice in chat`; comparison `Voice in chat (Text \| Voice)`; FAQ: switch Text \| Voice (no Dictate) |
| Composer Dictate gone | CODE PASS / UI auth-gated | Shared controls mount Speak only when `modality === "voice"`; zero `Dictate`/`onDictateError` in `apps/web` source. Authenticated `/ai` mic layout needs human confirm after login |
| Continuous duplex vs ChatGPT | **GAP (named)** | Live path remains Speak → composer → Send → `spoken_mode` + auto-TTS; provisional turn-taking not FE-wired |
| Minimum barge-in (Speak→stop TTS) | **BUILT on tip** | `VoiceInputButton.onListeningStart` → shared controls `onStop` when `ttsSpeaking` shipped in `ffe79feb`; acoustic AEC still **GAP** |
| Spoken register | **BUILT** | FE sends `spoken_mode` when Voice; Module D Register 5 in backend |
| Name self-recognition | **BUILT in stack / voice live NOT RUN** | Prompt injection present; needs human spoken exchange on tip |
| Tier-1 voice probe (API) | **PARTIAL** | `railway run … probe-tier1-voice-live.py`: status OK; STT skipped (no canned audio); TTS HTTP **402** @ ~533ms → verdict `PASS_CODE_BROWSER_FALLBACK` (browser TTS path; server TTS credit/gate blocked for probe token) |
