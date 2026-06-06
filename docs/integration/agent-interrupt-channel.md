# Human-in-the-loop interrupt channel (STA-108)

Operators can pause or cancel running agent work from the UI or Slack. Execution checks for interrupts before each workflow step and before each `invoke_tool` call.

## Signals

| Signal | Effect |
|--------|--------|
| `pause` | Stop before next step/tool; job/run status → `paused` |
| `cancel` | Stop before next step/tool; job/run status → `cancelled` |

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agent-interrupts` | Body: `{ targetType, targetId, signal }` |
| POST | `/api/agent-jobs/{id}/pause` | Pause async operator job |
| POST | `/api/agent-jobs/{id}/cancel` | Cancel async operator job (interrupt-aware) |

Target types: `agent_job`, `workflow_run`, `operator_session` (resolves to active job/run).

## Slack

`POST /api/slack/commands/interrupt` — configure slash command `/gravitre`:

```
/gravitre interrupt pause job <job-id>
/gravitre interrupt cancel run <run-id>
```

Set `SLACK_SIGNING_SECRET` on the backend. Org is resolved via active Slack connector `config.team_id`.

## Audit

- `agent.interrupt.requested`
- `agent.interrupt.acknowledged`
