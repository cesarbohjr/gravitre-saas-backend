# Platform cohesion (mandatory acceptance)

Every release item must **extend existing Gravitre contracts** — not add parallel stores, policy engines, or disconnected surfaces.

## Shared infrastructure (reuse, do not fork)

| Concern | Canonical contract | Consumers |
|---------|-------------------|-----------|
| Task / action lifecycle | `task_state.lifecycle_envelope`, `action_lifecycle`, `composer_envelope_from_turn` | Chat composer, voice, Activity, ROI |
| Write governance | `workflow_approval_scope`, `canvas_write_gate`, `react_write_gate`, `tool_service` | Agents, Plays, workflows, ReAct |
| Cost evidence | `model_calls` + `cost_attribution` (`run_id`, `turn_id`) | Billing, ROI, dashboards |
| Permissions | Org membership + write authority — **never** sentiment/context alone |
| Memory / ML | Source lifecycle + consent gates before promotion |

## PR checklist (required in matrix / PR body)

1. **Augments** — which existing features/paths this change extends.
2. **Contracts changed** — APIs, task_state keys, enums, audit actions.
3. **Cross-feature regression** — tests that prove chat/voice/workflow/ROI stay aligned.

## #429 cohesion map (draft)

| Change | Augments | Contract | Cross-feature tests |
|--------|----------|----------|---------------------|
| Idempotency ledger | `tool_service` write path | RPC + `claim_token` | PG acceptance, provider harness |
| Argument sealing | Approval scope (#413) | `allowed_write_targets` fingerprints | `test_write_approval_fingerprints`, canvas/ReAct gate |
| Sessions route | Release 1 auth | `requireAuthenticatedOrg` | Vitest sessions + require-authenticated-org |
| Lifecycle envelope | `conversation_state_service` | `lifecycle_envelope.customer_stage` | `test_lifecycle_envelope`, web `lifecycle-envelope` mapper |
| ReAct attribution | Unified turn + agent jobs | `cost_attribution` contextvars | `test_react_engine`, cost attribution tests |

**Feature complete** = coherent through chat, voice, workflows, and reporting — not an isolated endpoint green.
