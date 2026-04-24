# Connector Rate Limiting

## Risk identified
- Connector sends can spike and trigger upstream rate limits or abuse protections.
- Without back-pressure, approval execution can flood external systems.

## Current state
- No per-connector rate limiting before outbound Slack/Email/Webhook sends.
- Retries exist but do not cap overall send rate.

## Recommended fix
- Add DB-backed token bucket rate limiting per connector.
- On limit exceed, return HTTP 429 with `{ "detail": "Rate limit exceeded" }`.

## Implementation details
- Added `app/connectors/rate_limit.py` with DB-backed token bucket logic.
- Enforced in execute flow before:
  - `slack_post_message`
  - `email_send`
  - `webhook_post`
- Key format: `{org_id}:{step_type}:{connector_type}:{connector_id}`
- Limits are per-org + per-step + per-connector (DB-backed).
- Defaults (per connector):
  - Slack: burst 3, 1 req/sec
  - Email: burst 2, 0.2 req/sec
  - Webhook: burst 5, 2 req/sec
- This is distributed-safe (shared DB state).

## Future scaling notes
- Replace with distributed rate limiting (Redis) or queued sends.
- Add org-level quotas once multi-tenant limits are defined.
