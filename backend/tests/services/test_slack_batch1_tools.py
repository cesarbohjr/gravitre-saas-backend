"""Slack tool executor coverage for Batch 1 expansions."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="slack-1",
        environment_name="production",
        agent_id="agent-1",
    )


def test_slack_batch1_actions_registered():
    actions = list_registered_actions()
    assert "slack.users.info" in actions
    assert "slack.conversations.join" in actions


@patch("app.services.tool_service.write_audit_event")
@patch("app.services.agent_tool_permissions.list_agent_tool_permissions")
@patch("app.services.tool_service.enforce_rate_limit")
@patch("app.connectors.connector_tool_auth.resolve_slack_bot_token", return_value="xoxb-test")
@patch("app.services.tool_service.get_connector")
@patch("app.services.tool_service.get_user")
def test_slack_users_info(mock_get, mock_conn, _tok, _rate, mock_perms, _audit):
    mock_conn.return_value = {
        "id": "slack-1",
        "type": "slack",
        "status": "active",
        "environment": "production",
    }
    mock_perms.return_value = [{"connector_type": "slack", "scopes": ["slack:*"], "expires_at": None}]
    mock_get.return_value = {
        "ok": True,
        "user": {"id": "U1", "name": "ada", "profile": {"real_name": "Ada"}},
        "_latency_ms": 12,
    }
    result = invoke_tool(_ctx(), "slack.users.info", {"user": "U1", "connector_id": "slack-1"})
    assert result.success
    assert result.data["result_url"] == "https://app.slack.com/team/U1"
    assert "Ada" in result.data["summary"]


@patch("app.services.tool_service.write_audit_event")
@patch("app.services.agent_tool_permissions.list_agent_tool_permissions")
@patch("app.services.tool_service.enforce_rate_limit")
@patch("app.connectors.connector_tool_auth.resolve_slack_bot_token", return_value="xoxb-test")
@patch("app.services.tool_service.get_connector")
@patch("app.services.tool_service.join_conversation")
def test_slack_conversations_join(mock_join, mock_conn, _tok, _rate, mock_perms, _audit):
    mock_conn.return_value = {
        "id": "slack-1",
        "type": "slack",
        "status": "active",
        "environment": "production",
    }
    mock_perms.return_value = [{"connector_type": "slack", "scopes": ["slack:*"], "expires_at": None}]
    mock_join.return_value = {"ok": True, "channel": {"id": "C1"}, "_latency_ms": 9}
    result = invoke_tool(
        _ctx(), "slack.conversations.join", {"channel": "C1", "connector_id": "slack-1"}
    )
    assert result.success
    assert result.data["result_url"] == "https://app.slack.com/archives/C1"
