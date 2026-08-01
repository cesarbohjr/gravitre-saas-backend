# OutcomeEffect gate + agent lifecycle visibility

## Problem

False **COMPLETED** terminals recur when a vendor write returns success without a durable create (idempotent find, async accept, noop, or missing entity id). Apollo’s `already_existed` path was fixed locally; HubSpot/Clay/other connectors could still sell an unproven create as COMPLETED / `created_record`.

Agents also started and finished work with little or no bell/activity feed signal until Module A’s terminal fanout.

## Class gate (Part A)

`backend/app/services/connector_outcome_effects.py` owns vendor-wide classification:

| Effect | Meaning |
|--------|---------|
| `created` / `updated` | Mutating action with entity proof (`list_id` / `contact_id` / `id` / vendor URL) |
| `already_existed` | Idempotent find (Apollo label reuse, explicit flag) |
| `accepted_async` | Vendor queued/accepted; completion not proven |
| `noop` | Explicit no-op / unchanged |
| `unknown` | Mutating + success but **no** entity proof |
| `read` | Non-mutating action |

`coerce_terminal_status_for_effect` downgrades `completed` → `partial_success` when the action is mutating and effect ∈ `{already_existed, noop, accepted_async, unknown}`.

### Wiring

1. **`finalize_execution_outcome`** (Module A sole terminal writer) classifies + coerces **before** persist/audit/notify/learning. Puts `outcome_effect` on run metadata. Logs `execution_outcome_effect_gate_coerced`.
2. **BusinessOutcome projector** maps effects to honest kinds (`found_existing_record` / `other`) and verification methods (`module_a_idempotent_find`, `module_a_async_accepted`, `module_a_effect_unproven`). Unproven mutating creates never claim `module_a_verified_output` or `created_record`.
3. **Catalog HTTP executor** soft-tags write responses with `outcome_effect=created|unknown`.
4. **Chat connector** uses the same classifier; Apollo `already_existed` remains `partial_success`.

Module A remains the **only** terminal outcome writer for runs.

## Agent lifecycle notifications (Part B)

`backend/app/services/agent_activity_notifications.py`:

| Helper | Canonical event |
|--------|-----------------|
| `notify_agent_started` | `run_started` |
| `notify_agent_completed` | `task_completed` (mid-flight milestone) |
| `notify_agent_needs_approval` | `approval_needed` |

Aliases in `notification_emitter`: `agent_started` → `run_started`, `agent_discovery` / `agent_task_completed` → `task_completed`.

Call sites:

- `create_job` → “Agent task queued” (claim path skipped to avoid double spam)
- `maybe_create_agent_job_approval` → approval_needed to `requested_by`
- `AgentStepHandler.execute` → started before handoff; `task_completed` after success (failures left to Module A terminal)

Activity feed: after notification insert, entity types `{agent, agent_job, workflow_run, operator}` record with `source="agent"` so the Agents page can show work.

## What users see

- Idempotent / unproven / async vendor writes show **partial success**, not a green COMPLETED create.
- Business outcome cards say “found existing” or unproven effect instead of “created record” when proof is missing.
- Queued agent jobs and agent workflow steps emit bell notifications; agent-related activity appears on the activity feed.
- Run failures still surface only through Module A (`run_failed`), not a duplicate agent helper.

## Tests

- `tests/services/test_connector_outcome_effects.py` — classify/coerce + projector
- `tests/services/test_execution_outcome_effect_gate.py` — finalize coercion
- `tests/services/test_agent_activity_notifications.py` — helper → emit_notification
