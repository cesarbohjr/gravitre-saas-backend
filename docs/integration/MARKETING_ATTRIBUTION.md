# Marketing attribution workflow (STA-42)

Pre-built workflow: pull **GA4 campaign metrics** and **HubSpot leads**, summarize with the **Marketing Agent**, and post to **Slack**.

## Flow

```text
Manual / scheduled run
  → analytics.reports.run (GA4 campaigns + channels)
  → hubspot.contacts.search (recent leads)
  → agent step (Marketing Agent, briefing from prior steps)
  → slack.post_message (#marketing by default)
```

## Auto-setup

On **Connect HubSpot** or **Connect Google Analytics** (OAuth complete), the API upserts workflow **GA4 + HubSpot → Marketing summary → Slack** (`workflow_defs` + `workflows`).

Reconnect connectors after adding GA4, HubSpot, or Slack so step definitions pick up active connector IDs.

## Configuration

Stored on `organizations.settings.onboarding.marketing`:

| Key | Default | Description |
|-----|---------|-------------|
| `slack_channel` | `#marketing` | Slack channel for the digest |

Workflow id is stable per org: `demo_marketing_workflow_id` in onboarding settings.

## Run parameters

Optional overrides when executing the workflow (POST `/api/workflows/{id}/execute`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ga4_start_date` | `7daysAgo` | GA4 report start |
| `ga4_end_date` | `today` | GA4 report end |
| `hubspot_filter_groups` | (workflow default) | HubSpot search filters; use `enrich_marketing_attribution_parameters()` for a 7-day recency filter |

```python
from app.services.marketing_workflow_service import enrich_marketing_attribution_parameters

params = enrich_marketing_attribution_parameters({}, workflow_row)
```

## Manual execute

```http
POST /api/workflows/{demo_marketing_workflow_id}/execute
```

```json
{
  "parameters": {
    "ga4_start_date": "14daysAgo",
    "ga4_end_date": "today"
  }
}
```

Requires active **google_analytics** (with linked GA4 property), **hubspot**, and **slack** connectors.

## Code

- `backend/app/services/marketing_workflow_service.py`
- `backend/app/services/handoff_service.py` — `briefing_from_steps` on agent steps
- `backend/app/services/tool_service.py` — `message_from_step` for Slack steps
- `backend/app/services/hubspot_trigger_service.py` — setup on HubSpot connect
- `backend/app/connectors/google_analytics_oauth.py` — setup on GA4 connect

## Related

- [GOOGLE_ANALYTICS.md](./GOOGLE_ANALYTICS.md)
- [HUBSPOT_ACTIONS.md](./HUBSPOT_ACTIONS.md)
- [DEVOPS_WORKFLOW.md](./DEVOPS_WORKFLOW.md)
