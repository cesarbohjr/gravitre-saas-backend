from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.handoff_service import execute_agent_step_with_handoff
from app.services.marketing_workflow_service import (
    build_marketing_attribution_workflow_definition,
    enrich_marketing_attribution_parameters,
    ensure_marketing_attribution_workflow,
    marketing_agent_id,
    marketing_workflow_id,
)
from app.services.tool_service import params_for_step
from app.workflows.constants import SCHEMA_VERSION


def test_marketing_workflow_id_stable():
    org = str(uuid.uuid4())
    assert marketing_workflow_id(org) == marketing_workflow_id(org)


def test_marketing_agent_id_matches_seed_label():
    org_id = str(uuid.uuid4())
    assert marketing_agent_id(org_id) == str(
        uuid.uuid5(uuid.UUID(org_id), "gravitre-seed:agent:marketing")
    )


def test_build_definition_includes_ga4_hubspot_agent_slack():
    org_id = str(uuid.uuid4())
    definition = build_marketing_attribution_workflow_definition(
        org_id=org_id,
        ga4_connector_id="ga4-1",
        hubspot_connector_id="hubspot-1",
        slack_connector_id="slack-1",
        slack_channel="#marketing",
    )
    assert definition["schema_version"] == SCHEMA_VERSION
    types = [s["type"] for s in definition["steps"]]
    assert types == ["invoke_tool", "invoke_tool", "agent", "slack_post_message"]
    assert definition["steps"][0]["config"]["action"] == "analytics.reports.run"
    assert definition["steps"][1]["config"]["action"] == "hubspot.contacts.search"
    assert definition["steps"][2]["metadata"]["agent_id"] == marketing_agent_id(org_id)
    assert definition["steps"][2]["metadata"]["briefing_from_steps"] is True
    assert definition["steps"][3]["config"]["message_from_step"]["from_step"] == "marketing_summary"


def test_enrich_parameters_sets_ga4_defaults():
    workflow = {"config": {"marketing": {"slack_channel": "#growth"}}}
    out = enrich_marketing_attribution_parameters({}, workflow)
    assert out["ga4_start_date"] == "7daysAgo"
    assert out["ga4_end_date"] == "today"
    assert out["channel"] == "#growth"
    assert isinstance(out["hubspot_filter_groups"], list)


def test_params_for_slack_resolves_message_from_step():
    parameters = {}
    step_outputs = {"marketing_summary": {"summary": "Campaign A leads up 12%"}}
    params = params_for_step(
        "slack_post_message",
        {
            "connector_id": "slack-1",
            "channel": "#marketing",
            "message_from_step": {"from_step": "marketing_summary", "path": ["summary"]},
        },
        parameters,
        step_outputs=step_outputs,
    )
    assert params["message"] == "Campaign A leads up 12%"
    assert params["channel"] == "#marketing"


def test_ensure_marketing_workflow_upserts_rows():
    org_id = str(uuid.uuid4())
    client = MagicMock()
    wf_id = marketing_workflow_id(org_id)

    connectors = MagicMock()
    connectors.execute.side_effect = [
        MagicMock(data=[{"id": "ga4-conn"}]),
        MagicMock(data=[{"id": "hubspot-conn"}]),
        MagicMock(data=[{"id": "slack-conn"}]),
    ]
    orgs = MagicMock()
    orgs.execute.return_value = MagicMock(data=[{"settings": {"onboarding": {}}}])
    wf_defs = MagicMock()
    ui_workflows = MagicMock()
    client.table.side_effect = lambda name: {
        "connectors": connectors,
        "organizations": orgs,
        "workflow_defs": wf_defs,
        "workflows": ui_workflows,
    }[name]

    result = ensure_marketing_attribution_workflow(client, org_id)
    assert result == wf_id
    assert wf_defs.upsert.called
    assert ui_workflows.upsert.called


@patch("app.services.handoff_service.run_agent_task", new_callable=AsyncMock)
def test_agent_step_briefing_from_prior_steps(mock_run_agent_task):
    mock_run_agent_task.return_value = {
        "agent_id": "agent-1",
        "summary": "Top campaign: spring-launch",
        "recommended_actions": [],
        "confidence": 80,
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "agent-1", "name": "Marketing Agent", "status": "active", "systems": ["hubspot"]}]
    )
    settings = MagicMock()
    step_def = {
        "metadata": {
            "agent_id": "agent-1",
            "task": "Summarize attribution",
            "briefing_from_steps": True,
        }
    }
    step_outputs = {
        "ga4_report": {"report": {"rows": []}},
        "hubspot_leads": {"search": {"results": []}},
    }

    import asyncio

    output = asyncio.run(
        execute_agent_step_with_handoff(
            settings,
            org_id=str(uuid.uuid4()),
            user_id="user-1",
            run_id="run-1",
            step_id="marketing_summary",
            step_def=step_def,
            parameters={},
            step_outputs=step_outputs,
            client=client,
        )
    )

    assert output["summary"] == "Top campaign: spring-launch"
    mock_run_agent_task.assert_awaited_once()
    call_kwargs = mock_run_agent_task.await_args.kwargs
    assert call_kwargs["briefing"] is not None
    assert any(a["step_id"] == "ga4_report" for a in call_kwargs["briefing"]["artifacts"])
