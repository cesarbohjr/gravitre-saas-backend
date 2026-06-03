from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext


def test_jira_actions_registered():
    actions = list_registered_actions()
    assert "jira.issues.create" in actions
    assert "jira.issues.assign" in actions
    assert "jira.issues.transition" in actions
    assert "jira.issues.comment" in actions


def test_jira_issues_create_requires_project_key():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32, encryption_key="")
    tool_ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-devops",
        environment_name="production",
    )
    conn = {"id": "jira-conn", "type": "jira", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_jira_session",
                return_value=("token", "cloud-1", None),
            ):
                with patch("app.services.tool_service.write_audit_event"):
                    with patch(
                        "app.services.agent_tool_permissions.list_agent_tool_permissions",
                        return_value=[
                            {
                                "connector_type": "jira",
                                "scopes": ["jira:issues:write"],
                                "expires_at": None,
                            }
                        ],
                    ):
                        result = invoke_tool(tool_ctx, "jira.issues.create", {"summary": "Only summary"})
    assert result.success is False
    assert result.error_code == "validation_error"


def test_jira_issues_comment_success():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32, encryption_key="")
    tool_ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-devops",
        environment_name="production",
    )
    conn = {"id": "jira-conn", "type": "jira", "status": "active", "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.services.tool_service.ensure_jira_session",
                return_value=("token", "cloud-1", None),
            ):
                with patch(
                    "app.services.tool_service.add_issue_comment",
                    return_value={"id": "c1"},
                ):
                    with patch("app.services.tool_service.write_audit_event"):
                        with patch(
                            "app.services.agent_tool_permissions.list_agent_tool_permissions",
                            return_value=[
                                {
                                    "connector_type": "jira",
                                    "scopes": ["jira:issues:write"],
                                    "expires_at": None,
                                }
                            ],
                        ):
                            result = invoke_tool(
                                tool_ctx,
                                "jira.issues.comment",
                                {"issue_key": "ENG-9", "body": "Update from agent"},
                            )
    assert result.success is True
    assert result.data["comment"]["id"] == "c1"
