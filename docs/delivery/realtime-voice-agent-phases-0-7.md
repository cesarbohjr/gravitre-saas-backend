# Real-time voice agent — Phases 0–7 delivery report

**Live tip:** `fd012939577df76408d37f1ef5612a763ea69095` (Railway health `git_sha` confirmed)  
**Prior tip:** `94a6a875e8d80a70f6d243c4ba1de02ca32c2f92`

## Verification labels

| Item | Status |
|------|--------|
| Unit tests (error classes, turn-taking, spoken register, COGS math, TTS/STT mocks) | **BUILT-AND-UNIT-TESTED** — 18 passed |
| Phase 0 error-class surfacing (402 ≠ 502) | **FULLY LIVE-VERIFIED** on tip `fd012939…` — `POST /api/voice/tts` → **HTTP 402**, `error_class=billing`, `billing_issue=true`, upstream `paid_plan_required` / request_id `ed898ec81009228ee44a27fba3808b10` |
| Phase 0 live TTS 200 + real audio bytes | **PENDING FUNDED-ACCOUNT VERIFICATION** — ElevenLabs still rejects library voices: Free plan cannot use library voices via API (`paid_plan_required`). Same key; needs paid ElevenLabs plan (not only ElevenAPI credit top-up) |
| Phase 0 latency baselines on prod | **PENDING** until TTS 200 |
| Phase 0 text TTFT gate on live tip | **PENDING** separate prove |
| Phase 1 streaming session path | **BUILT-AND-UNIT-TESTED** (`/api/voice/session/turn` NDJSON + `execute_task_streaming(spoken_mode=True)`) |
| Phase 2 provisional turn-taking | **BUILT-AND-UNIT-TESTED** (Eager/Normal/Patient; Normal default) |
| Phase 3 naming / spoken register / library / design APIs | **BUILT**; live preview/audio **PENDING** until ElevenLabs paid plan |
| Phase 4 text⇄voice toggle | **BUILT** (agent chat); entitlement decision flagged |
| Phase 5 write confirm policy | **BUILT** (unchanged `nl_yes_same_path_as_text`); live voice-triggered write **PENDING** |
| Phase 6 GIBE surface tag + acoustic async | **BUILT-AND-UNIT-TESTED** (heuristic features; honesty labeling) |
| Phase 7 COGS + Billing usage fields | **PARTIALLY LIVE-VERIFIED** — `GET /api/billing` on tip returns `voice_minutes_billing_visible=true`, `included_voice_minutes=60`, `totals.voice_minutes=0`. Stripe meter seed still needs `STRIPE_SECRET_KEY` run + Railway env attach |

## Phase 0 — TTS error handling

- Upstream **402** → HTTP **402**, `error_class=billing`, clear “billing issue” detail (not generic 502).
- Upstream 401 / 429 / other → distinct classes; genuine outages remain 502 `service_failure`.
- Default TTS model: `eleven_flash_v2_5` (legacy turbo alias accepted).
- **Do not swap Railway `ELEVENLABS_API_KEY`.** Re-prove when ElevenAPI credits land.

## Phase 7 — COGS & pricing (flagged for review)

Gravitre stack is **ElevenAPI Flash TTS + Deepgram streaming STT**, not ElevenAgents hosting.

| Component | Rate | Source |
|-----------|------|--------|
| Deepgram streaming | $0.0077/min | deepgram.com/pricing |
| ElevenLabs Flash | $0.05/1k chars ≈ $0.0375/min continuous speech | elevenlabs.io/pricing/api |
| Blended duplex minute | $0.0077 + 0.5×$0.0375 = **$0.02645** | math |
| Proposed overage | **$0.12/min** ≈ **4.5×** blended COGS | tunable |
| ElevenAgents reference | $0.08/min (+ Deepgram → $0.0877; ×3.5 ≈ $0.31) | not used by this architecture |

**Included minutes/month:** Node **60** / Control **300** / Command **1200**.

Seed script: `python backend/scripts/stripe_seed_voice_minutes_meter.py`  
Env: `STRIPE_VOICE_MINUTES_METER_EVENT_NAME`, `STRIPE_VOICE_MINUTES_METERED_PRICE_ID`.

## Entitlement decision needed (Phase 4.2)

Voice API remains gated by Meson addon **`voice_interface`**. Confirm whether live staff text⇄voice should:

1. Keep requiring `voice_interface`, or  
2. Be plan-included, or  
3. Use a separate entitlement  

Do not assume — surfaced on `GET /api/voice/status` as `entitlement_decision_needed`.

## Custom Voice reuse

Saved Custom Voices persist to `agent_custom_voices` (org-scoped) and are **reusable across agents in the same org**.

## Phase 6.3 — other ML (report only, not built)

- Multi-party diarization — later  
- Device AEC for barge-in — client/device  
- Audio language-ID auto-switch — nice-to-have  

## v0 handoff

Functional pipeline ships first. Waveform/orb polish, light/dark screenshot pass, and visual card refinement are the **v0 handoff** after funded-account live verification — no data-contract changes expected.

## Honest latency targets

- Deepgram STT ~150–300ms  
- ElevenLabs Flash first-byte ~75–255ms  
- End-to-end ~700–900ms (“feels human”) — not sub-300ms  
