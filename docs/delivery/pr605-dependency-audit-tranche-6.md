# PR #605 — Tranche 6: registered route call chains and database/event consumer evidence
Date: 2026-11-05. Deployed source baseline `557be844f191767ea51c9f1d1d4958e5b046ca53`. Read-only GitHub and connected Supabase metadata; Supabase production binding **not yet established**.

## Proven route registration and concrete chains
1. `backend/app/main.py` registers `assistant.router`, `pipecat_voice.router`, `voice_gateway.router` with FastAPI via `app.include_router`. This improves on file-count inference: these router modules are mounted in source. Production request traffic remains unverified.
2. `POST /api/assistant/chat` → `assistant_chat` (`backend/app/routers/assistant.py`, near line 1311) → JWT user, org and environment dependencies, AI killswitch and streaming response. The route explicitly treats JWT-validated org membership as authoritative, not request-body org hint. Follow-up code-level routing through model/agent/connector services still needs full branch-by-branch analysis.
3. `GET /api/assistant/conversation/{conversation_id}/state` → explicit ownership check in `conversations` by conversation, org and user → `ConversationStateService.get_task_state` → reconstructed durable execution result. This is an actual handler-to-database read chain.
4. `POST /api/assistant/conversation/{conversation_id}/execute` → authenticated org and explicit confirm check → ownership query against `conversations` → imports `ConversationalExecutionService`, `ChatConnectorExecutionService`, `ChatOrchestrationService`, `ConversationStateService`. Further execution paths need branch-level tracing; import presence alone does not establish every call.
5. `/api/voice/pipecat/ws` → `pipecat_voice.py` WebSocket endpoint with JWT/seat/org voice authorization imports; `/api/voice-gateway/pstn/media/{session_id}` is a separate PSTN WS path. Browser `/api/voice/session/turn` Next.js handler proxies via `voiceFastApiBase` to FastAPI.
6. `backend/app/main.py` lifespan explicitly starts `start_temporal_worker` as an asyncio task when `use_temporal`; otherwise logs fallback to asyncio scheduling **without retry on restart** for named workloads. Code explicitly notes some jobs remain in-process even in Temporal mode. This is a real ownership and durability distinction.
7. `ExecutionOutcome` → `publish_outcome` → org-scoped in-process asyncio queues for live subscribers; code comments identify `workflow_runs` outbox event `execution.outcome_finalized` as durable copy. **Correction to prior audit**: in-memory fanout is not the sole source of terminal outcomes, so do not claim all outcomes are lost on overflow. Verify durable event's actual transaction/consumer/replay before certifying delivery.

## Database metadata (connected project `smyeexlrqdpymwjmgzqu`; production binding unverified)
Read-only `pg_constraint`, `pg_class`, `pg_policy`, `pg_trigger` metadata reveals:
- `conversation_messages.conversation_id` → `conversations`; `conversations` → `organizations` and `auth.users`.
- `approvals.run_id` → `runs`; `run_approvals.run_id` → `workflow_runs`. This is **two approval-to-run foreign-key domains**. Migration must preserve both until all producers/consumers reconciled.
- `run_steps.run_id` → `runs`; multiple other operational tables reference `workflow_runs`, including `agent_handoffs`, `operator_actions`, `workflow_compensation_records`, `work_object_events`, `approval_batches` and `model_calls`. Replacing `workflow_runs` without migration would break these dependencies.
- `workflow_active_versions` → `workflows` and `workflow_versions`; `workflow_edges` → `workflow_nodes` and `workflow_defs`. There are multiple related workflow model families.
- Inspected tables `workflow_runs`, `runs`, `run_steps`, `approvals`, `run_approvals`, `conversations`, `conversation_messages`, `audit_events`, `audit_logs`, `play_runs`, `domain_event_outbox`, `webhook_event_receipts` all have RLS enabled. **RLS enabled is not proof of correct isolation.**
- `domain_event_outbox` and `webhook_event_receipts` have zero direct `pg_policy` rows and zero non-internal triggers in this project; with RLS enabled, this can be intentional service-role-only design. Check grants, service-role bypass, security-definer functions and actual consumers before classifying as a defect.
- `workflow_runs` has 2 direct policies and 3 non-internal triggers; `runs` has 1 direct policy and 1 non-internal trigger. Trigger definitions and side effects are not yet audited.

## New gaps / engineering changes
| ID | Priority | Finding | Required fix / acceptance |
|---|---|---|---|
| ECO-037 | P0 | Mounted assistant/voice routes confirmed, but only selected handler chains traced. | Generate **executable** FastAPI route inventory and Next.js route map, then automated call-graph with dynamic import and event edges; reconcile against production traffic. |
| ECO-038 | P0 | Dual approval FK domains: `approvals→runs` and `run_approvals→workflow_runs`. | Map exact approval issuers, consumers and state transitions; ensure no bypass between APIs before unifying. |
| ECO-039 | P0 | Numerous dependent tables reference `workflow_runs`. | Require FK, trigger, view, function, RLS, audit, notification and migration-impact proof before any run-store cutover. |
| ECO-040 | P0 | In-process outcome notifications coexist with documented durable `workflow_runs` outbox. | Separate UI best-effort from durable terminal state; inspect outbox write atomicity, consumer registration, retry, dead letter, idempotency and replay. |
| ECO-041 | P0 | Temporal startup is conditional, with explicit asyncio fallback lacking restart retries. | Verify actual production config/worker and workload criticality; add restart-safe durable scheduling for work that must survive crashes. |
| ECO-042 | P1 | RLS is enabled on sampled tables; outbox/receipt tables have zero direct policies. | Inspect role grants and security-definer access; test authorized tenant and service-role operations. Do not infer security defect from policy count alone. |
| ECO-043 | P1 | Frontend backend URL helper chooses Railway-generated origin in some cases even when public API custom domain is configured. | Trace rewrite and proxy routes to actual resolved target; add preview/prod contract tests, sanitized origin telemetry, explicit fail-closed config. |

## Exact remaining blockers to full gate closure
- The full route-to-handler-to-service graph is **not yet complete**: no runtime-instrumented all-routes export, dynamic caller coverage, frontend component callers, or complete transitive dependencies.
- The inspected Supabase project's production binding is not established; do not label schema findings definitively production.
- No event subscriber inventory, durable outbox consumer trace, database trigger definitions, function calls, grants or real traffic samples yet.
- No exact-head automated tests or deployment route probes executed. No code or production changes.
