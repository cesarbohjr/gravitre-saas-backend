from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.services.devops_workflow_service import (
    build_devops_incident_workflow_definition,
    devops_workflow_id,
    enrich_devops_incident_parameters,
    ensure_devops_incident_workflow,
)
from app.services.tool_service import params_for_step
from app.workflows.constants import SCHEMA_VERSION


def test_devops_workflow_id_stable():
    org = str(uuid.uuid4())
    assert devops_workflow_id(org) == devops_workflow_id(org)


def test_build_definition_includes_jira_and_slack_steps():
    definition = build_devops_incident_workflow_definition(
        jira_connector_id="jira-1",
        slack_connector_id="slack-1",
        jira_project_key="ENG",
        slack_channel="#eng-alerts",
        jira_assignee_account_id="acc-99",
    )
    assert definition["schema_version"] == SCHEMA_VERSION
    types = [s["type"] for s in definition["steps"]]
    assert types == ["invoke_tool", "invoke_tool", "slack_post_message"]
    assert definition["steps"][0]["config"]["action"] == "jira.issues.create"
    assert definition["steps"][2]["config"]["channel"] == "#eng-alerts"


def test_enrich_parameters_maps_incident_to_jira_and_slack():
    workflow = {
        "config": {
            "devops": {
                "slack_channel": "#eng-alerts",
                "jira_project_key": "ENG",
            }
        }
    }
    base = {
        "incident": {"id": "P1", "summary": "DB down", "urgency": "high", "html_url": "https://pd.example/P1"},
        "pagerduty_event": {"incidentId": "P1", "summary": "DB down"},
    }
    out = enrich_devops_incident_parameters(base, workflow)
    assert "[PD] DB down" in out["jira_summary"]
    assert "P1" in out["jira_description"]
    assert "#eng-alerts" in out["channel"]
    assert "DB down" in out["slack_message"]
    assert "https://pd.example/P1" in out["slack_message"]


def test_params_for_invoke_tool_resolves_step_output():
    parameters = {"jira_summary": "Test"}
    step_outputs = {"jira_create": {"issue": {"key": "ENG-42", "id": "10042"}}}
    params = params_for_step(
        "invoke_tool",
        {
            "action": "jira.issues.assign",
            "connector_id": "jira-1",
            "param_sources": {
                "issue_key": {"from_step": "jira_create", "path": ["issue", "key"]},
                "account_id": "acc-1",
            },
        },
        parameters,
        step_outputs=step_outputs,
    )
    assert params["issue_key"] == "ENG-42"
    assert params["account_id"] == "acc-1"


def test_ensure_devops_workflow_upserts_rows():
    org_id = str(uuid.uuid4())
    client = MagicMock()
    wf_id = devops_workflow_id(org_id)

    connectors = MagicMock()
    connectors.execute.side_effect = [
        MagicMock(data=[{"id": "jira-conn"}]),
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

    result = ensure_devops_incident_workflow(client, org_id)
    assert result == wf_id
    assert wf_defs.upsert.called
    assert ui_workflows.upsert.called
