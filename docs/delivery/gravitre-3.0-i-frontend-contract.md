# Gravitre 3.0-I frontend contract (2026-09-24)

The Gravitre 3.0 Plus frontend agent owns Window Manager, voice orb/visualizer, AI workspace, artifact panel, React Flow, and Intelligence composition. This file is the **spoken WRITE state / SSE** delta only.

## Unchanged

- `POST /api/assistant/chat` with `spoken_mode: true` still uses `execute_task_streaming`.
- Pending writes remain `task_state.pending_task` (`type=connector_action`, `status=awaiting_confirm`).
- Existing `data-intelligence` / text-delta SSE events.

## Binding fields on `pending_task` (optional for UI)

- `id` / `pending_action_id`
- `org_id`, `actor_id`, `conversation_id`
- `invoke_action` (frozen ActionSpec key)
- `expires_at` (ISO-8601; confirm after expiry is refused)
- `status`: `awaiting_confirm` | `executing` | `completed` | `cancelled` | …

## Spoken decisions (task_state / extras)

- `spoken_write_decision`: `hold_commit` | `clarify` | `foreign_actor` | `already_done` | `already_claimed` | `pending_expired` | …
- `provider_invoked: false` on hold, clarify, stale, unauthorized
- Confirm still executes only through `claim_pending_write` → `invoke_tool`

Do not invent Enable toggles, prices, or Certified badges. Do not treat this as a second voice runtime.
