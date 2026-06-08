# EU AI Act agent decision transparency (STA-112)

Per automated operator decision, Gravitre records an exportable transparency log with input context, model metadata, tools invoked, human overrides, and outcome.

## When logs are created

| Source | Trigger |
|--------|---------|
| `operator_auto_execute` | Policy-gated auto-execute attempts a plan step (STA-106) |

Workflow run parameters carry `_transparency_log_id` so tool invocations append to the same record. Logs finalize when the workflow run completes.

## Record fields

| Field | Description |
|-------|-------------|
| `inputContext` | Operator, plan, step, session context (PII redacted) |
| `modelInfo` | Planning model metadata when available |
| `toolsInvoked` | Tool actions with connector, success, latency |
| `humanOverride` | Approval/rejection when a human gates the decision |
| `outcome` | Run status, errors, workflow run id |

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/enterprise/transparency-logs` | List recent decision logs |
| GET | `/api/enterprise/transparency-logs/export` | Download JSON bundle (admin) |

## Audit

- `enterprise.transparency.decision_logged`
- `enterprise.transparency.exported`

## Related

- STA-106 auto-execute — creates autonomous decisions
- STA-81 / STA-82 — PII redaction in exported bundles
- STA-108 human-in-the-loop — approval flows populate `humanOverride`
