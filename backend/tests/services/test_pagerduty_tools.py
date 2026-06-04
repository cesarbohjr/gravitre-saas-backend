from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext


def test_pagerduty_actions_registered():
    actions = list_registered_actions()
    assert "pagerduty.incidents.acknowledge" in actions
    assert "pagerduty.incidents.add_note" in actions
    assert "pagerduty.incidents.escalate" in actions


def test_pagerduty_acknowledge_requires_incident_id():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32, encryption_key="")
    tool_ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-devops",
        environment_name="production",
    )
    conn = {
        "id": "pd-conn",
        "type": "pagerduty",
        "status": "active",
        "environment": "production",
        "config": {"pagerduty_requester_email": "ops@example.com"},
    }
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_pagerduty_session",
                return_value=("token", None),
            ):
                with patch("app.services.tool_service.write_audit_event"):
                    with patch(
                        "app.services.agent_tool_permissions.list_agent_tool_permissions",
                        return_value=[
                            {
                                "connector_type": "pagerduty",
                                "scopes": ["pagerduty:incidents:write"],
                                "expires_at": None,
                            }
                        ],
                    ):
                        result = invoke_tool(tool_ctx, "pagerduty.incidents.acknowledge", {})
    assert result.success is False
    assert result.error_code == "validation_error"


def test_pagerduty_add_note_success():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32, encryption_key="")
    tool_ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-devops",
        environment_name="production",
    )
    conn = {
        "id": "pd-conn",
        "type": "pagerduty",
        "status": "active",
        "environment": "production",
        "config": {"pagerduty_requester_email": "ops@example.com"},
    }
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_pagerduty_session",
                return_value=("token", None),
            ):
                with patch(
                    "app.services.tool_service.add_incident_note",
                    return_value={"note": {"id": "N1"}},
                ):
                    with patch("app.services.tool_service.write_audit_event"):
                        with patch(
                            "app.services.agent_tool_permissions.list_agent_tool_permissions",
                            return_value=[
                                {
                                    "connector_type": "pagerduty",
                                    "scopes": ["pagerduty:incidents:write"],
                                    "expires_at": None,
                                }
                            ],
                        ):
                            result = invoke_tool(
                                tool_ctx,
                                "pagerduty.incidents.add_note",
                                {"incident_id": "P99", "content": "On it"},
                            )
    assert result.success is True
    assert result.data["note"]["id"] == "N1"
