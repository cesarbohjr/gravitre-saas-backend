# Phase 6: Observability Upgrades

## Risks
- No step timing makes root‑cause analysis slow.
- Connector latency isn’t measured consistently.
- Logs lack consistent identifiers.

## Current State
- Step timing captured via `workflow.execute.step_timing` audit events.
- Connector latency recorded for Slack/Email/Webhook sends.
- RAG retrieval latency logged + stored in `rag_retrieval_logs`.

## Implementation Details
- Step timing:
  - `execute_workflow_steps` computes per‑step `duration_ms`.
  - Written via audit event `workflow.execute.step_timing`.
- Connector latency:
  - Slack: `_latency_ms` from API client
  - Email: `latency_ms` returned by SMTP send
  - Webhook: `response_time_ms` recorded in audit metadata
- Log fields:
  - `request_id`, `org_id`, `run_id`, `step_id` included in execute step logs

## Future Notes
- Add trace IDs for cross‑service correlation.
- Export step timing to metrics tables.
# Phase 6: Observability Upgrades

## Risk
- Missing timing and correlation fields make production triage slow.
- Connector latency and step duration are hard to diagnose without structured data.

## Implementation Summary
- Added per-step timing audit events (`workflow.execute.step_timing`).
- Added connector send latency to audit metadata (Slack/Email/Webhook).
- Standardized log fields: request_id, org_id, run_id, step_id.

## Implementation Details
- Step timing + logs: `backend/app/workflows/execute.py`
  - Logs include `request_id`, `org_id`, `run_id`, `step_id`, `duration_ms`
- Connector latency:
  - Slack: `backend/app/connectors/slack.py`
  - Email: `backend/app/connectors/email.py`
  - Webhook: `backend/app/workflows/execute.py`
- RAG retrieval latency already captured in `rag_retrieval_logs`.

## Future Scaling Notes
- Add tracing IDs to connector requests if upstream supports it.
- Emit structured logs to external sink (e.g., ELK/Datadog).
