# DevOps cross-tool workflow (STA-39)

End-to-end procedure when a PagerDuty incident fires: create a Jira ticket, optionally assign an owner, and post to Slack.

## Flow

```text
PagerDuty incident.triggered
  → workflow run (trigger_type: pagerduty)
  → jira.issues.create (invoke_tool)
  → jira.issues.assign (invoke_tool, if assignee configured)
  → slack.post_message (#eng-alerts by default)
```

## Auto-setup

On **Connect PagerDuty** (OAuth complete), the API:

1. Upserts workflow **PagerDuty incident → Jira + Slack** (`workflow_defs` + `workflows`).
2. Adds a PagerDuty trigger binding: `incident.triggered` → that workflow.

Requires active **Jira** and **Slack** connectors in the same org (same environment when possible). Steps are omitted until the connector exists; reconnect PagerDuty after adding Jira/Slack to refresh the definition.

## Configuration

Stored on `organizations.settings.onboarding.devops`:

| Key | Default | Description |
|-----|---------|-------------|
| `jira_project_key` | `ENG` | Jira project for new incidents |
| `slack_channel` | `#eng-alerts` | Slack channel for alerts |
| `jira_assignee_account_id` | (none) | Jira Cloud account ID; omit to skip assign step |

Workflow id is stable per org: `demo_devops_workflow_id` in onboarding settings.

## Run parameters

PagerDuty webhooks normalize to `incident` / `pagerduty_event`. The workflow enriches:

- `jira_summary`, `jira_description`
- `slack_message`, `channel`

## Manual trigger binding

```http
PUT /api/connectors/{pagerduty_connector_id}/pagerduty-triggers
```

```json
{
  "triggers": [
    {
      "event": "incident.triggered",
      "workflow_id": "<demo_devops_workflow_id>",
      "active": true,
      "label": "DevOps incident"
    }
  ]
}
```

## Code

- `backend/app/services/devops_workflow_service.py`
- `backend/app/workflows/handlers.py` — `invoke_tool` step
- `backend/app/services/pagerduty_trigger_service.py` — parameter enrichment
- `backend/app/routers/connector_oauth.py` — setup on PagerDuty connect

## Related

- [PAGERDUTY_TRIGGERS.md](./PAGERDUTY_TRIGGERS.md)
- [JIRA_ACTIONS.md](./JIRA_ACTIONS.md)
- [PAGERDUTY_ACTIONS.md](./PAGERDUTY_ACTIONS.md)
