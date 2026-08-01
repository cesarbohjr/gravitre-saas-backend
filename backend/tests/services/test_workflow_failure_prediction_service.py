"""STA-122: Predictive workflow failure detection service."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.services.workflow_failure_prediction_service import (
    FailurePredictionError,
    dismiss_failure_alert,
    extract_step_requirements,
    list_failure_alerts,
    scan_org_failure_predictions,
    scan_workflow_failure_predictions,
)


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.is_.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[])
    mock.insert.return_value = insert_mock

    delete_mock = MagicMock()
    delete_mock.eq.return_value = delete_mock
    delete_mock.execute.return_value = MagicMock(data=[])
    mock.delete.return_value = delete_mock

    update_mock = MagicMock()
    update_mock.eq.return_value = update_mock
    update_mock.execute.return_value = MagicMock(data=[])
    mock.update.return_value = update_mock

    return mock


def test_extract_step_requirements_invoke_tool():
    definition = {
        "schema_version": "v1",
        "steps": [
            {
                "id": "s1",
                "name": "Update contact",
                "type": "invoke_tool",
                "config": {
                    "action": "hubspot.contacts.update",
                    "connector_id": "conn-1",
                },
                "metadata": {"agent_id": "agent-1"},
            }
        ],
    }
    reqs = extract_step_requirements(definition)
    assert len(reqs) == 1
    assert reqs[0]["stepId"] == "s1"
    assert reqs[0]["action"] == "hubspot.contacts.update"
    assert reqs[0]["connectorType"] == "hubspot"
    assert reqs[0]["agentId"] == "agent-1"


def test_extract_step_requirements_skips_platform_council_step():
    definition = {
        "schema_version": "v1",
        "steps": [
            {
                "id": "council",
                "name": "Council",
                "type": "council",
                "config": {"objective": "Enroll or nurture"},
            }
        ],
    }
    assert extract_step_requirements(definition) == []


def test_list_failure_alerts_serializes_rows():
    alerts_table = _table(
        [
            {
                "id": "alert-1",
                "org_id": "org-1",
                "workflow_id": "wf-1",
                "step_id": "s1",
                "connector_id": None,
                "alert_type": "step_failure_risk",
                "severity": "medium",
                "title": "Elevated failure rate",
                "message": "Step failed often",
                "evidence": {"failureRate": 0.3},
                "confidence": 0.72,
                "status": "open",
                "predicted_at": "2026-06-09T00:00:00+00:00",
                "dismissed_at": None,
                "created_at": "2026-06-09T00:00:00+00:00",
                "updated_at": "2026-06-09T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = alerts_table
    alerts = list_failure_alerts(client, "org-1", workflow_id="wf-1")
    assert alerts[0]["alertType"] == "step_failure_risk"
    assert alerts[0]["workflowId"] == "wf-1"


def test_dismiss_failure_alert_not_found():
    alerts_table = _table([])
    client = MagicMock()
    client.table.return_value = alerts_table
    with pytest.raises(FailurePredictionError, match="not found"):
        dismiss_failure_alert(client, "org-1", "missing")


@patch("app.services.workflow_failure_prediction_service.write_audit_event")
@patch("app.services.workflow_failure_prediction_service.get_active_workflow_version")
@patch("app.services.workflow_failure_prediction_service._build_predictive_alerts")
def test_scan_workflow_failure_predictions_persists_alerts(mock_build, mock_version, mock_audit):
    mock_version.return_value = {
        "definition": {
            "schema_version": "v1",
            "steps": [{"id": "s1", "name": "Step", "type": "invoke_tool", "config": {}}],
        }
    }
    mock_build.return_value = [
        {
            "org_id": "org-1",
            "workflow_id": "wf-1",
            "step_id": "s1",
            "connector_id": None,
            "alert_type": "connector_missing",
            "severity": "critical",
            "title": "Missing hubspot connector",
            "message": "No connector",
            "evidence": {},
            "confidence": 0.92,
            "status": "open",
            "predicted_at": "2026-06-09T00:00:00+00:00",
        }
    ]

    alerts_table = _table([])
    alerts_table.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "alert-1",
                "org_id": "org-1",
                "workflow_id": "wf-1",
                "step_id": "s1",
                "connector_id": None,
                "alert_type": "connector_missing",
                "severity": "critical",
                "title": "Missing hubspot connector",
                "message": "No connector",
                "evidence": {},
                "confidence": 0.92,
                "status": "open",
                "predicted_at": "2026-06-09T00:00:00+00:00",
                "dismissed_at": None,
                "created_at": "2026-06-09T00:00:00+00:00",
                "updated_at": "2026-06-09T00:00:00+00:00",
            }
        ]
    )

    client = MagicMock()
    client.table.return_value = alerts_table
    settings = Settings()

    summary = scan_workflow_failure_predictions(
        client,
        settings,
        "org-1",
        "wf-1",
        environment_name="production",
        actor_id="user-1",
    )
    assert summary["alertCount"] == 1
    assert summary["riskScore"] > 0
    assert summary["alerts"][0]["alertType"] == "connector_missing"
    mock_audit.assert_called_once()


def test_find_active_connector_id_resolves_searchconsole_alias():
    """Tool prefix searchconsole must match Connectors hub type google_search_console."""
    from app.services.workflow_failure_prediction_service import _find_active_connector_id

    table = _table([{"id": "gsc-1"}])
    client = MagicMock()
    client.table.return_value = table

    found = _find_active_connector_id(
        client, "org-1", "searchconsole", environment_name="production"
    )
    assert found == "gsc-1"
    assert any(
        call.args and call.args[0] == "type" and call.args[1] == "google_search_console"
        for call in table.eq.call_args_list
    )


def test_build_predictive_alerts_searchconsole_uses_hub_label():
    from app.services.workflow_failure_prediction_service import _build_predictive_alerts

    definition = {
        "steps": [
            {
                "id": "gsc-1",
                "name": "List GSC Sites",
                "type": "invoke_tool",
                "config": {"action": "searchconsole.sites.list"},
            },
            {
                "id": "ah-1",
                "name": "Brand Radar Overview",
                "type": "invoke_tool",
                "config": {"action": "ahrefs.brand_radar.overview"},
            },
        ]
    }
    client = MagicMock()
    client.table.side_effect = lambda _name: _table([])
    settings = Settings()

    with patch(
        "app.services.workflow_failure_prediction_service._find_active_connector_id",
        return_value=None,
    ):
        alerts = _build_predictive_alerts(
            client,
            settings,
            "org-1",
            "wf-1",
            definition,
            environment_name="production",
        )
    titles = {alert["title"] for alert in alerts}
    assert "Missing google search console connector" in titles
    assert "Missing ahrefs credential" in titles
    gsc = next(a for a in alerts if "google search console" in a["title"])
    assert gsc["evidence"]["connectorType"] == "google_search_console"


@patch("app.services.workflow_failure_prediction_service._find_active_connector_id", return_value=None)
def test_build_predictive_alerts_skips_knowledge_base_sources(_mock_find):
    """FRED/NVD/CISA KEV are Marketplace knowledge-base packs — not Connectors hub."""
    from app.services.workflow_failure_prediction_service import _build_predictive_alerts

    definition = {
        "steps": [
            {
                "id": "fred-1",
                "name": "Fetch FRED GDP",
                "type": "invoke_tool",
                "config": {"action": "fred.series.get"},
            },
            {
                "id": "nvd-1",
                "name": "Fetch NVD CVE",
                "type": "invoke_tool",
                "config": {"action": "nvd.cves.search"},
            },
            {
                "id": "kev-1",
                "name": "Fetch CISA KEV sample",
                "type": "invoke_tool",
                "config": {"action": "cisa_kev.catalog.list"},
            },
            {
                "id": "zd-1",
                "name": "List Zendesk Tickets",
                "type": "invoke_tool",
                "config": {"action": "zendesk.tickets.list"},
            },
        ]
    }
    client = MagicMock()
    client.table.side_effect = lambda _name: _table([])
    settings = Settings()

    alerts = _build_predictive_alerts(
        client,
        settings,
        "org-1",
        "wf-1",
        definition,
        environment_name="production",
    )
    titles = {alert["title"] for alert in alerts}
    assert "Missing fred connector" not in titles
    assert "Missing nvd connector" not in titles
    assert "Missing cisa_kev connector" not in titles
    assert "Missing zendesk connector" in titles


@patch("app.services.workflow_failure_prediction_service.load_oauth_tokens")
@patch("app.services.workflow_failure_prediction_service.resolve_connector_auth_status")
def test_build_predictive_alerts_auth_expiry(mock_auth_status, mock_tokens):
    from app.services.workflow_failure_prediction_service import _build_predictive_alerts

    mock_auth_status.return_value = "connected"
    mock_tokens.return_value = {"expires_at": time.time() + 3600}

    definition = {
        "steps": [
            {
                "id": "s1",
                "name": "HubSpot step",
                "type": "invoke_tool",
                "config": {
                    "action": "hubspot.contacts.update",
                    "connector_id": "conn-1",
                },
            }
        ]
    }

    connectors = _table([{"id": "conn-1", "type": "hubspot", "vendor": "hubspot", "status": "active"}])
    runs = _table([])
    steps = _table([])
    client = MagicMock()

    def table(name):
        if name == "connectors":
            return connectors
        if name == "workflow_runs":
            return runs
        if name == "workflow_steps":
            return steps
        if name == "agent_tool_permissions":
            return _table([])
        return _table([])

    client.table.side_effect = table
    settings = Settings()

    alerts = _build_predictive_alerts(
        client,
        settings,
        "org-1",
        "wf-1",
        definition,
        environment_name="production",
    )
    types = {alert["alert_type"] for alert in alerts}
    assert "auth_expiry" in types


def test_list_failure_alerts_missing_table_returns_empty():
    alerts_table = _table([])
    alerts_table.execute.side_effect = Exception('relation "workflow_failure_alerts" does not exist')
    client = MagicMock()
    client.table.return_value = alerts_table
    assert list_failure_alerts(client, "org-1") == []


@patch("app.services.workflow_failure_prediction_service.write_audit_event")
@patch("app.services.workflow_failure_prediction_service.scan_workflow_failure_predictions")
@patch("app.services.workflow_failure_prediction_service.list_workflows")
def test_scan_org_failure_predictions_aggregates_workflows(mock_list, mock_scan, mock_audit):
    mock_list.return_value = [
        {"id": "wf-1", "name": "Onboarding", "status": "active"},
        {"id": "wf-2", "name": "Archived", "status": "archived"},
    ]
    mock_scan.side_effect = [
        {
            "workflowId": "wf-1",
            "alertCount": 1,
            "riskScore": 25,
            "alerts": [{"severity": "high", "alertType": "auth_expiry"}],
            "scannedAt": "2026-06-09T00:00:00+00:00",
            "environment": "production",
        }
    ]

    client = MagicMock()
    settings = Settings()
    summary = scan_org_failure_predictions(
        client,
        settings,
        "org-1",
        environment_name="production",
        actor_id="user-1",
    )

    assert summary["workflowCount"] == 1
    assert summary["scannedCount"] == 1
    assert summary["alertCount"] == 1
    assert summary["workflows"][0]["workflowName"] == "Onboarding"
    mock_scan.assert_called_once()
    mock_audit.assert_called_once()
