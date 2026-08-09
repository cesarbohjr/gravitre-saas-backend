# Agent chat — shared voice TTS + 402 presence wiring

**Date:** 2026-08-08  
**Goal:** Close the agent-chat gap vs the proven `/api/voice/tts` pipeline (Phase 0), without a parallel voice stack.

## Phase 1 — Gap (confirmed)

| Capability | `/ai` (main chat) | Agent chat (before) |
|------------|-------------------|---------------------|
| Chat + `spoken_mode` | No | Yes (`/api/chat` → `execute_task_streaming(spoken_mode=True)`) |
| TTS playback | Manual Read aloud → `synthesizeViaElevenLabs` → `POST /api/voice/tts` | Missing (no auto-play) |
| 402 / `error_class=billing` | Swallowed as `null` → browser fallback | Never hit |
| Presence strip amber | N/A (not mounted) | Component supported `billing`; **unwired** |

Streaming session `POST /api/voice/session/turn` (NDJSON + progressive TTS) remains backend-built; agent chat reuses the **same** chat backbone + **same** batch TTS endpoint already live-proven for Phase 0 — not a second client implementation.

## Phase 2 — Wiring (this change)

1. **`synthesizeViaElevenLabsDetailed`** — structured ok/error; parses `error_class` / `billing_issue` (incl. live `http_exception_handler` envelope).
2. **`useAgentVoicePlayback`** — auto-play helper; **no** browser fallback on billing 402.
3. **Agent chat page** — after stream completes in Voice modality, speak last assistant text via `/api/voice/tts` with `agent_id`; drive `<VoiceSessionPresence billing={…} />` from real TTS errors.
4. **QA force** — `X-Gravitre-QA-Force-Voice-Error: billing` (gated by `unified_turn_qa_hooks_enabled`), same pattern as unified-turn QA headers. UI trigger: `?qaForceVoiceError=billing`.

## Phase 3 — Verification evidence

| Check | Result |
|---|---|
| Railway tip (voice QA hook) | **PASS** — `GET /health` `git_sha=1378ca16cd2a1ba5c2bb00c780ac677cb6031d04` (backend voice QA force). Follow-up `f2e7dac6` Railway **SKIPPED** (web/docs-only). |
| Vercel tip | **PASS** — production READY `dpl_7uPqrB9L4oiJVwzEyfdRAzCJ2KjS` on `f2e7dac6` (`gravitre.app`) |
| Unit (voice QA hooks) | **PASS** — 5 passed |
| Unit (FE TTS error parse) | **PASS** — 4 passed |
| QA-force 402 API | **PASS** — `railway run python scripts/prove-agent-chat-voice-402-qa-force.py` → `pass:true`, HTTP 402, `error_class=billing`, `billing_issue=true`, detail contains `qa_force_voice_error=billing` (evidence: `docs/delivery/agent-chat-voice-402-qa-force.json` @ `2026-08-09T04:15:28Z`) |
| Amber presence (agent chat) | Wired to real TTS billing signal; trigger via `?qaForceVoiceError=billing` or natural ElevenLabs 402 |
| Successful TTS audio bytes | **PENDING FUNDED-ACCOUNT** — live `/api/voice/tts` still returns natural 402 `paid_plan_required` (ElevenLabs Free cannot use library voices). Same blocker as Phase 0. Wiring path identical; audio prove waits for paid ElevenLabs plan. |
| Main-chat `/ai` regression | Read aloud still uses `synthesizeViaElevenLabs` compatibility wrapper (null on failure → browser fallback). No transport change. |

```bash
# Unit
cd backend && python -m pytest tests/services/test_voice_qa_hooks.py -q
cd apps/web && npx vitest run __tests__/lib/tier1-voice-client-tts-error.test.ts

# Live API
railway run python scripts/prove-agent-chat-voice-402-qa-force.py

# Live UI amber
# https://gravitre.app/agents/<id>/chat?qaForceVoiceError=billing
# → Voice toggle → send message → amber "Voice paused — credits needed"
# → remove query / Text mode → amber clears
```

## Non-goals

- Does not replace `/ai` Read aloud behavior (legacy null → browser fallback preserved).
- Does not require swapping agent chat transport to `/session/turn` NDJSON.
