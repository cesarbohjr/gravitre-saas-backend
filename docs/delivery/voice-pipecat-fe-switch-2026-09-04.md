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

## Live evidence (2026-09-04)

| Layer | Tip / deploy | Verdict | Evidence |
|-------|--------------|---------|----------|
| Vercel production FE | `6b98dbe6` (`dpl_FrL6DUcFx1RA4QyCwvDDSoa9enNi`) | **READY** | Aliased to `gravitre.app`; typecheck fix for Pipecat WS `Record` parse |
| Pipecat WS + write-governance + status honesty | Railway `8ac01d95` | **PASS** | `voice-pipecat-phase1-live.json` — `default_orchestration=pipecat`, `session.ready`, PCM, `CognitiveTurnKernel`, `nl_yes_same_path_as_text` |
| HTTP duplex regression | Railway `5275df04` (pre tip advance) | **PASS** | `voice-duplex-one-brain-live.json` — barge-in, continuation, write governance, CognitiveTurnKernel |

**Human hear/barge-in on `/ai`:** still required before closing “voice fixed.”

**Status honesty (live):** Railway tip `8ac01d95` — `/api/voice/status` reports `default_orchestration=pipecat` with `pipecat_enabled=true` (`voice-pipecat-phase1-live.json` after tip advance).
