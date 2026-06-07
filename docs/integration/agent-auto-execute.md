# Policy-gated auto-execute (STA-106)

Operators (UI agents) can run approved plan steps without manual confirmation when org policy allows.

## Execution modes

| Mode | Behavior |
|------|----------|
| `plan_only` | Default. Plans always require human confirmation (never auto-execute prompt). |
| `auto_with_approval` | Eligible steps queue for approval automatically; no manual click to submit approval. |
| `auto_trusted_scopes` | Steps matching trusted scopes run immediately after plan creation. |

## API

| Method | Path | Description |
|--------|------|-------------|
| PUT | `/api/agents/{id}/auto-execute` | Admin: set mode + trusted scopes |
| PATCH | `/api/operators/{id}` | Also accepts `execution_mode`, `auto_execute_trusted_scopes` |

## Audit

- `operator.auto_execute.enabled` — mode/scopes changed
- `operator.auto_execute.attempted` — auto-run or approval queue after plan creation

## Prerequisites

STA-90 model allowlist policy (`GET/PUT /api/settings/model-policy`) should be configured before enabling auto-execute in production.
