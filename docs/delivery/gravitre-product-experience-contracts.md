# Gravitre product-experience contracts (core → 3.0 Plus)

Version: 2026-09-24. Canonical functional state. Presentation owned by the 3.0 Plus frontend agent. Do not redesign Window Manager, voice orb, or Intelligence layouts here.

## Shared identity

| Field | Owner | Notes |
|---|---|---|
| `conversation_id` | core | Survives text, HTTP Talk, Pipecat WS |
| `execution_plan.plan_id` | core | SoT. Follow-ups keep the same id |
| `pending_task` / `pending_action` | core | Spoken and typed confirm the same claim |
| `execution_observations[]` | core | Canonical outcomes |
| `work_artifacts[]` / `durable_deliverable` | core | Bound to `plan_id`, `observation_ids` |
| `proactive_operator[]` | core | Ranked READ notices; `write_allowed` always false |

## Voice

Pipecat `/api/voice/pipecat/ws` uses the same `conversation_id` as chat. Confirm speech claims the frozen PendingAction. Ambiguous speech does not execute.

## Artifacts

`work_artifacts[].kind`: `executive_report` \| `table` \| `brief` \| `action_plan` \| `research_summary`. Markdown in `metadata.code`. `exportable: true`. Reconstruct via GET `/api/assistant/conversation/{id}/state` — no provider re-invoke.

Browser artifact panel remains **BLOCKED_EXTERNAL** (expired trial). API durability is independent.

## Computer / browser

`classify_execution_strategy`: `api_native` (ActionSpec) \| `browser_cdp` (public URL READ via existing browser agent) \| `computer_use` (Playwright interact, flag + approval) \| `hybrid`. Observation: `{success,url,action,screenshot_digest,dom_excerpt,cdp_trace_id,approval_id}`. No paid CDP vendor started.

## Proactive attention

GET/chat `What needs my attention?` → `execution_path=proactive_attention_3_0_j`. Zero notices when evidence is missing. Positive notices require source-backed readiness/auth evidence.

## Show the work

Deferred. Do not emit a production checklist stream yet.
