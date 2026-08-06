# Prompt 3 Phase 3 — Tier 1 voice (TTS + STT)

**Status:** SHIPPED (code path) — paid providers env-gated  
**Architecture:** bolted onto existing unified-turn text chat (not realtime conversational)  
**Tip:** pending deploy of this commit

## Providers

| Direction | Provider | Endpoint |
|-----------|----------|----------|
| TTS (read aloud) | ElevenLabs (`eleven_turbo_v2_5`) | `POST /api/voice/tts` |
| STT (mic) | Deepgram Nova-2 | `POST /api/voice/stt` |
| Fallback | Browser Web Speech / speechSynthesis | client-only when keys absent |

### 3-voice selection (ElevenLabs)

| Key | Default voice id | Role |
|-----|------------------|------|
| `rachel` | `21m00Tcm4TlvDq8ikWAM` | Clear professional female |
| `adam` | `pNInz6obpgDQGcFmaJgB` | Clear professional male |
| `josh` | `TxGEqnHWrfWFTfGW9XjX` | Conversational male |

Override via `ELEVENLABS_VOICE_RACHEL` / `_ADAM` / `_JOSH`. Default key: `ELEVENLABS_DEFAULT_VOICE=rachel`.

## Write-approval decision (explicit)

**Choice: NL “yes” through the exact same text approval path** (`awaiting_confirm` → `CONFIRM_PATTERN` / pending-reply classifier → execute), with tap-to-confirm (`POST .../execute` `{confirm:true}`) still available.

Spoken confirmation alone is **not** a bypass. STT only produces composer text; that text must clear the same server-side write gate as typing. `catalog_write_authority` and Module A outcome records are untouched.

## Env

```
ELEVENLABS_API_KEY=
ELEVENLABS_TTS_MODEL=eleven_turbo_v2_5
ELEVENLABS_DEFAULT_VOICE=rachel
DEEPGRAM_API_KEY=
DEEPGRAM_STT_MODEL=nova-2
```

## Latency honesty (Tier 1)

Industry realtime conversational bar: **sub-300ms**.  
Tier 1 expected band: **STT (200–800ms) + model TTFT (~500–1800ms from Prompt 1 tip) + TTS (200–800ms)** → typically **1–3.5s** end-to-end, not sub-300ms parity.

Measure via `X-Voice-Latency-Ms` (TTS) and `latency_ms` (STT) once keys are live.

## Live verification

1. `GET /api/voice/status` → `tts_enabled` / `stt_enabled` when keys present  
2. Read aloud on assistant message → ElevenLabs audio (or browser fallback)  
3. Mic → transcript into composer → same `sendMessage` / `/api/chat` path  
4. Voice write: utterance that triggers `awaiting_confirm`; spoken/typed **yes** or tap Confirm required — no silent execute  
5. Confirm no regression to `catalog_write_authority`

When keys are absent: status reports disabled; browser fallback remains; live paid path = **NOT_RUN** until Railway secrets are set.
