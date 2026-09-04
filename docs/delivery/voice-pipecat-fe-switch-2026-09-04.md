# FE switch to Pipecat WS (2026-09-04)

## Change

`useVoiceDuplexSession` now selects orchestration from `/api/voice/status`:

| Condition | Path |
|-----------|------|
| `pipecat_enabled` + available (and not `forceHttpDuplex`) | Browser PCM → `wss://…/api/voice/pipecat/ws` |
| Otherwise | Legacy Deepgram browser WS → `POST /api/voice/session/turn` |

Shared surfaces (`/ai`, `agents/[id]/chat`) pick this up automatically. E2E duplex harness forces HTTP via `forceHttpDuplex: true`.

## Supporting pieces

- `apps/web/lib/pipecat-voice-client.ts` — WS URL (token + org), PCM encode/decode, interrupt
- Status `pipecat_ws_hint` for absolute `wss://api.gravitre.app` (overridable with `NEXT_PUBLIC_VOICE_WS_BASE`)
- Backend serializer: interim transcripts + `assistant_text` transport messages for orb/provisional UX

## Verify

1. With `VOICE_PIPECAT_ENABLED=true`, open `/ai` → Talk — confirm audible reply (PCM path).
2. Mid-reply speak to barge-in (`interrupt`).
3. Flag off (or `forceHttpDuplex`) still uses HTTP duplex.

**Live tip at FE ship:** record after Vercel/web deploy; API tip already has Pipecat at `5b578100+`.
