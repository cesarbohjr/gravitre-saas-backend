# PR #605 — Dependency audit tranche 4: duplex client, state persistence, autonomous verification
Date: 2026-11-04. Source baseline `557be844f191767ea51c9f1d1d4958e5b046ca53`. Static wiring investigation; production runtime behavior not yet proven.

## Findings and remediation proposals
| ID | Priority | Source evidence | Observed wiring / hypothesis | Required engineering response |
|---|---|---|---|---|
| ECO-022 | P0 | `apps/web/hooks/use-voice-duplex-session.ts` (2,432 lines) | One large React hook manages voice duplex behavior; contains legacy endpoint-delay and interruption-intent helpers, WebSocket handling, and buffer-source playback references. **Complex state ownership is a confirmed maintainability risk**, not proof of a specific audio defect. | Draw client voice state machine and event ownership, test old/new session transitions, split transport, mic, transcript, playback and cancellation only with contract tests. |
| ECO-023 | P0 | `apps/web/lib/voice-pcm-player.ts` (455 lines) | Both AudioWorklet and BufferSource PCM player implementations are present, alongside jitter scheduling and ducking controls. | Verify actual production selection and fallback reasons, buffer starvation, gain transitions, playback completion and sample rate. Do not remove BufferSource until compatibility matrix is proven. |
| ECO-024 | P0 | `apps/web/lib/pipecat-voice-client.ts` (212 lines) | WebSocket URL resolution uses environment-configured base or production API URL; exposes PCM16 encoding/decoding and interruption/playback-start messages. | Verify domain routing and authorization for browser→Railway WS, correlation of audio frames and interruption events, proxy and reconnect behavior. |
| ECO-025 | P0 | `backend/app/services/pipecat_voice/transcript_relay.py` (146 lines) | Relay classifies non-turn finals and forwards finals through urgent transport; coordinates with server session state. | Trace interim/final STT identity, deduplication across relay/client/history and stale-session suppression; reproduce repeated short words. |
| ECO-026 | P0 | `backend/app/services/conversation_state_service.py` (763 lines) | Conversation state persists via repository/Supabase client, uses scoped per-conversation `threading.RLock`, I/O pool, task-state patches and compare-and-set pending transitions. | Verify multi-instance/distributed consistency: process-local locks do not by themselves serialize across Railway replicas. Test CAS semantics, competing turns, crash/restart and pending-write idempotency. This is a risk, **not evidence of a race**. |
| ECO-027 | P0 | `backend/app/services/autonomous_execution_loop.py` (175 lines) | Execution loop references durable work session `stop_reason`, `verify_before_complete`, execution plans, and explicit provider-write verification. | Preserve evidence-before-completion invariant; test read/write outcomes, partial results, stale observations, approval, cancellation and restart. |
| ECO-028 | P1 | `backend/app/services/execution_plan_service.py` (634 lines) | ExecutionStep/Observation/Plan, continue/replan/reconcile, terminal and stalled-plan helpers exist; imports conversational confirmation pattern. | Map how conversation phrases feed state transitions and verify spoken/written approvals cannot be inferred from ambiguous utterances. |

## Primary → secondary → tertiary edges established by source inspection
1. Browser voice session hook → WebSocket transport and mic/PCM playback → AudioWorklet/BufferSource, jitter scheduler, duck gain, telemetry, Web Audio context.
2. Browser Pipecat client → backend WS URL resolution, access token and selected organization → authenticated production API gateway and server-side session.
3. Pipecat transcript relay → server session classification and urgent transport message → client transcript state, chat history and model turn ownership (last two links require caller-level verification).
4. ConversationStateService → scoped in-process locks and I/O pool → Supabase-backed persistence and CAS pending-state operations.
5. AutonomousExecutionLoop → durable session verification and execution-plan steps → provider write evidence and terminal outcomes.
6. ExecutionPlanService → conversational confirmation semantics → plan reconciliation and terminal status.

## Required tests before any refactor
- Two concurrent turns for one org/conversation, including two processes, stale revision and simultaneous approve/revoke; verify no lost updates or unauthorized writes.
- Crash/restart between approval, provider request, provider acknowledgment and durable terminal write; assert idempotent recovery.
- Voice 20-minute soak after deployment, synthetic PCM starvation/underrun premerge, AudioWorklet vs BufferSource selection, barge-in, reconnect and cancellation.
- STT duplicate short-word finals and relay/client persistence parity; no false new user turns from backchannels.
- Approval phrase ambiguity and voice/text parity, with explicit scope binding and no write before authorization.
- End-to-end trace IDs across client audio frames, backend WS, model turn, tools, TTS and final outcome.

## Important limitations
Static source confirms these functions and imports, not production call counts, actual WebSocket endpoints, selected PCM renderer, runtime flags, or distributed consistency defects. Gate remains open until live deployment mapping and exact-head tests establish those facts.
