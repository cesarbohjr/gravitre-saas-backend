# Phase 6: Connector Dispatch + Throttling

## Risks
- Process-local throttling diverges across instances.
- Connector spikes can exceed third‑party limits.
- No centralized guardrails across workers.

## Current State
- DB-backed token bucket added in `supabase/migrations/20250220000002_phase6_connector_rate_limits.sql`.
- Enforcement in `app/connectors/rate_limit.py` via RPC.

## Implementation Details
- Table: `connector_rate_limits`
- Token bucket key: `{org_id}:{step_type}:{connector_type}:{connector_id}`
- RPC: `consume_connector_token(...)` updates tokens atomically.
- Default limits are defined in `app/connectors/dispatch.py`.
- Rate-limit violations raise `RateLimitError`, which maps to HTTP 429 in execute paths.

## Why This Works
- Shared DB state makes throttling consistent across instances.
- Locks are handled server-side in Postgres.

## Future Notes
- Add per‑org overrides (table-driven limits).
- Add queue-based dispatch if connector volume increases.
# Phase 6: Connector Dispatch + Throttling

## Risk
- Process-local throttling does not prevent bursts across multiple instances.
- Uncoordinated dispatch can exceed upstream rate limits.

## Implementation Summary
- Replaced process-local token buckets with DB-backed token buckets.
- Throttling is keyed by org + step + connector type + connector id.
- Connector execute path enforces the shared rate limit and returns 429 on limit.

## Implementation Details
- Migration: `supabase/migrations/20250220000002_phase6_connector_rate_limits.sql`
  - Table: `connector_rate_limits`
  - Function: `consume_connector_token(...) RETURNS boolean`
- Runtime enforcement: `backend/app/connectors/rate_limit.py`
  - `enforce_rate_limit(client, org_id, step_type, connector_type, connector_id)`
- Default capacities/refill: `backend/app/connectors/dispatch.py`
 - Key format: `{org_id}:{step_type}:{connector_type}:{connector_id}`

## Notes
- This is Option 1 (DB-backed token bucket).
- No new worker infrastructure required; dispatch remains inline.

## Future Scaling Notes
- Add per-connector overrides in config table.
- Add per-org burst limits if abuse appears.
