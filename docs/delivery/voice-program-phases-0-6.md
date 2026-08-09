# Voice program — Phases 0–6 (2026-08-09)

Standing scope distinction:
- **Internal voice** = staff talking to their org AI (Deepgram STT + ElevenLabs TTS, Text|Voice, Dictate). Never call-center.
- **External voice connectors** = Twilio / Vapi (and similar) inbound/outbound telephony via governed catalog connectors.

## Phase 0 — Honest disconnect (before fixes)

### Current production code (tip `34006e15` at investigation)

| Surface | Dictate | Text\|Voice | `spoken_mode` | Auto-TTS |
|---|---|---|---|---|
| `/ai` main chat | Labeled Dictate present | **Absent** | **Absent** | Manual Read aloud only |
| `/agents/[id]/chat` | Present | Present | Present when Voice | Auto via `useAgentVoicePlayback` |
| Extension chat | Absent | Absent | Absent | Absent |

### Prior “live-verified” claims — what they actually verified

| Report | Claim | Actually verified against | Disconnect |
|---|---|---|---|
| `realtime-voice-agent-phases-0-7.md` | Phase 0 FULLY LIVE-VERIFIED TTS 402; Phase 4 Text⇄Voice **BUILT** | `/api/voice/tts` API + **agent chat** toggle | Not main `/ai` Text\|Voice |
| `agent-chat-voice-tts-402-wiring.md` | Agent chat TTS/402 wiring; gap table says `/ai` has **no** `spoken_mode` | Agent chat + QA-force 402 API | Explicitly left `/ai` without Voice modality |
| `billing-addons-topup-voice-discoverability.md` | Dictate label on `/ai`; Text\|Voice on agent chat | Discoverability ship — Dictate label only on `/ai` | “Chat discoverability SHIPPED” ≠ Voice modality on `/ai` |

**Verdict:** Prior work correctly live-verified **API TTS** and **agent-chat** Text\|Voice. Main `/ai` was never given the Text\|Voice / `spoken_mode` pipeline. Dictate was present but **broken in prod** (see Phase 1).

### Dictate live failure (reproduced)

- `POST /api/voice/stt` → **500** `INTERNAL_ERROR`
- Railway log: `UnboundLocalError: cannot access local variable 'get_supabase_client'` in `post_stt` (local import inside `analyze_acoustic` block shadows module import)
- Control: `POST /api/voice/stt-form` → **200** (Deepgram path works; same audio)

---

## Phase deliverables (this ship)

| Phase | Status | Notes |
|---|---|---|
| 0 Honest disconnect | **DONE** | Prior “live-verified” was API TTS + agent chat; `/ai` lacked Text\|Voice/`spoken_mode`; Dictate 500 from `UnboundLocalError` |
| 1 Dictate STT fix | **FIXED** | Removed shadowing import in `post_stt`; structured STT errors + webm mime on client |
| 2 Main chat voice | **SHIPPED** | `/ai` landing + workspace use `SharedChatComposerControls` + `spoken_mode` + auto-TTS |
| 3 Unify agent chat chrome | **SHIPPED** | Agent chat imports same shared controls + matching composer surface tokens |
| 4 Drift CI | **SHIPPED** | `scripts/check-chat-surface-drift.mjs` in CI; deliberate violation → exit 1 |
| 5 External connectors | **TWILIO FIRST** | Real Twilio REST executor + write approval + Call/Message SID verification; Vapi catalog scaffold (`shipped=False`) next |
| 6 Billing reframe | **SHIPPED** | `voice_minutes_billing_visible=false`; Voice Minutes card/top-up hidden; Settings toggle reframed as policy (not cost) |

### Scope distinction (UI)

- Internal: Text\|Voice / Dictate = staff talking to org AI
- External: Twilio / Vapi connector actions = real phone/SMS to people outside the org (approval-gated)
