# Module A outcome-event schema changelog

Training substrate for future Module C models. Bump `OUTCOME_SCHEMA_VERSION`
in `backend/app/services/execution_outcome.py` when the wire shape changes.

## 1.0.0 (2026-07-19)

Initial versioned shape emitted by `finalize_execution_outcome()`:

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | string | Semver, currently `1.0.0` |
| `run_id` | uuid \| null | Canonical run identity (shared by `workflow_runs` / `runs`) |
| `org_id` | uuid | |
| `status` | enum | `completed` \| `failed` \| `cancelled` \| `partial_success` |
| `source` | enum | `chat_orch` \| `assistant_chat` \| `canvas` \| `api` \| `worker` \| `assignment` |
| `actor_id` | uuid \| null | |
| `workflow_id` | uuid \| null | |
| `error_summary` | string \| null | Failed/cancelled only |
| `timestamp` | ISO-8601 | Terminal time |
| `verified_output` | object | `summary`, `result_url`, `external_url`, `entity_type`, `entity_id`, `integration` |
| `audit_action` | string \| null | e.g. `workflow.execute.failed` |
| `notification_event` | string \| null | e.g. `run_failed` |
| `learning_event` | string \| null | e.g. `workflow_failed` |
| `fanout` | object | Booleans for each fanout step |

Stored on `intelligence_outcome_events.metadata.schema_version` and published
on the outcome event bus for live subscribers.
