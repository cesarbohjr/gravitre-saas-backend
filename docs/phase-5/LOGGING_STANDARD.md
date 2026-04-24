# Logging Standard

## Risk identified
- Missing correlation fields make incidents hard to triage.
- Logging PII or secrets violates security requirements.
- High-volume endpoints can overwhelm logs.

## Current state
- Structured logger injects `request_id`, `user_id`, `org_id`.
- Logging is present on workflow endpoints; connector sends avoid message bodies.

## Recommended fix
- Standardize required fields and forbidden content.
- Enforce correlation ID propagation (`x-request-id`) end-to-end.
- Add sampling rules for noisy endpoints (metrics).

## Implementation details
- Required fields on request logs:
  - `request_id`, `org_id`, `user_id` (if available), `path`, `method`, `status_code`, `latency_ms`
- Correlation:
  - Accept inbound `x-request-id` and echo in responses.
  - Include `request_id` on all audit and connector logs.
- Forbidden content:
  - Tokens, secrets, email addresses, message bodies, payloads, queries, URLs
- Metrics endpoints:
  - Sample at low rate in production (e.g., 10%) or log only aggregated stats.
- Connector logging guardrails:
  - Log only hashes, domains, and IDs; never raw payloads.

## Future scaling notes
- Add structured JSON log output for centralized ingestion.
- Introduce log redaction middleware for defense in depth.
