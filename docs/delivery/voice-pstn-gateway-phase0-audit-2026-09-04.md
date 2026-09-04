# Phase 0 — PSTN voice architecture audit (2026-09-04)

## Twilio connector (shipped vs scaffold)

| Action | Status |
|--------|--------|
| `twilio.calls.create/get/list` | **Shipped** — real REST, approval-gated create, Call SID verification |
| `twilio.messages.create/get/list` | **Shipped** — same pattern |
| `twilio.accounts.get` | **Shipped** |
| Verify / Studio / Conversations | **Scaffold** — generic catalog_http stub |
| Vapi (4 actions) | **Scaffold** — `shipped=False`, no dedicated executor |
| Inbound webhooks | **Was missing** — added `/api/webhooks/twilio/voice/*` in this ship |

## CognitiveTurnKernel voice path (browser)

- STT: **Deepgram** live WS (`linear16` @ 16 kHz) — browser-direct via `use-voice-duplex-session`
- TTS: **ElevenLabs** stream (`audio/mpeg`) — progressive via `stream_voice_turn_events`
- Barge-in: client abort + `request_turn_cancel` (Redis-backed)
- Reasoning: `execute_task_streaming(spoken_mode=True)` → CognitiveTurnKernel

## PSTN repoint verdict

**Partial reuse.** The brain (`stream_voice_turn_events`, turn-taking, write gates) is transport-agnostic.
**New bridging required:** Twilio Media Streams (mulaw 8 kHz) ↔ server-side Deepgram WS ↔ ulaw TTS egress.
Browser WebSocket + HTML Audio cannot be repointed at PSTN.

This ship adds:
- `voice_gateway_service.start_voice_session_outbound`
- `pstn_voice_bridge.run_mid_call_turn` → same kernel, `tts_output_format=ulaw_8000`
- Deepgram PSTN encoding: `mulaw` @ 8 kHz (no second STT vendor)

## Live verification

**NOT RUN** — real outbound PSTN call + mid-call calendar tool requires Twilio prod credentials and human confirmation.
