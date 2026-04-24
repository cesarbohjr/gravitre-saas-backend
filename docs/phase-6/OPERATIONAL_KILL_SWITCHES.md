# Phase 6: Operational Kill Switches

## Switches
- `DISABLE_EXECUTE=true` — blocks execute runs and approvals from starting execution.
- `DISABLE_CONNECTORS=true` — blocks connector steps (Slack/Email/Webhook).
- `DISABLE_INGESTION=true` — blocks ingestion enqueue and worker processing.

## Behavior
- Default is `false` (off).
- When enabled, affected endpoints return HTTP 503 with a clear message.
- Switches are global (org‑safe) and require restart to take effect.

## Notes
- Use for incident response and maintenance windows.
- Re‑enable and re‑run approvals once a switch is cleared.
# Phase 6: Operational Kill Switches

## Risk
- Emergency shutdown paths are required for safe operations.
- Without switches, external side effects cannot be halted quickly.

## Implementation Summary
- Added config-driven kill switches:
  - `DISABLE_EXECUTE`
  - `DISABLE_CONNECTORS`
  - `DISABLE_INGESTION`
- Default off; org-safe (global).

## Behavior
- `DISABLE_EXECUTE=true`
  - Blocks execute endpoint and approval-triggered execution.
- `DISABLE_CONNECTORS=true`
  - Blocks workflows containing external connector steps.
- `DISABLE_INGESTION=true`
  - Blocks `/api/rag/ingest` and ingestion worker start.

## Implementation Details
- Settings: `backend/app/config.py`
- Routing guards: `backend/app/routers/workflows.py`, `backend/app/routers/rag_admin.py`
- Worker guard: `backend/app/rag/worker.py`

## Future Scaling Notes
- Add per-org kill switches if needed for multi-tenant emergencies.
