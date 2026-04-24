# Phase 9 — Operator Guardrails

## Guardrail Principles

- **No auto-execution**: AI suggestions require human confirmation before any execution-capable action.
- **Approvals enforced**: Approval requirements are never hidden or bypassed.
- **Org + environment scoped**: All data and actions are scoped to auth-derived `org_id` and `X-Environment`.
- **Secrets are write-only**: Connector secrets are never returned to the UI.
- **No PII leakage**: Avoid raw message text, raw chunk content, or full payloads in operator UIs.

## Backend Guardrails

- Policy evaluation and approval resolution remain in the workflow policy engine.
- Operator endpoints are additive and read-only (except action-plan generation).
- Action plans provide labels and requirements but do not execute anything.

## Frontend Guardrails

- All calls are routed through Next.js proxy routes.
- Environment is visible at all times.
- Action cards display approval/admin/execution requirements.
- Confirmation UI is required before any executable action is shown.

## Known Limitations

- Guardrails are currently advisory in action plan output; execution still relies on existing policy enforcement.
- Some related entity relationships are best-effort and may be incomplete.

