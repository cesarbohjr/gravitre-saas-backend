from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.agent_tool_permissions import (
    assert_agent_tool_permission,
    default_demo_scopes_for_system,
    required_scopes_for_action,
    upsert_agent_tool_permission,
)
from app.services.tool_service import invoke_tool
from app.services.tool_types import ToolContext, ToolPermissionDeniedError


@pytest.fixture
def tool_ctx() -> ToolContext:
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32)
    client = MagicMock()
    return ToolContext(
        settings=settings,
        client=client,
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-1",
    )


def test_required_scopes_for_slack():
    scopes = required_scopes_for_action("slack.post_message")
    assert "slack:messages:write" in scopes


def test_default_demo_scopes_hubspot():
    scopes = default_demo_scopes_for_system("hubspot")
    assert "hubspot:contacts:read" in scopes
    assert "hubspot:*" in scopes


def test_assert_skips_without_agent_id():
    settings = SimpleNamespace(disable_connectors=False)
    ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
    )
    assert_agent_tool_permission(ctx, "slack.post_message", None, "slack")


def test_assert_denied_without_permissions(tool_ctx: ToolContext):
    tool_ctx.client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=[])
    )
    with pytest.raises(ToolPermissionDeniedError, match="no tool permissions"):
        assert_agent_tool_permission(tool_ctx, "slack.post_message", None, "slack")


def test_assert_granted_by_connector_type(tool_ctx: ToolContext):
    tool_ctx.client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        MagicMock(
            data=[
                {
                    "connector_id": None,
                    "connector_type": "slack",
                    "scopes": ["slack:messages:write"],
                    "expires_at": None,
                }
            ]
        )
    )
    assert_agent_tool_permission(tool_ctx, "slack.post_message", None, "slack")


def test_upsert_updates_existing_row():
    client = MagicMock()
    select_chain = client.table.return_value.select.return_value
    select_chain.eq.return_value = select_chain
    select_chain.is_.return_value = select_chain
    select_chain.limit.return_value.execute.return_value = MagicMock(data=[{"id": "perm-1"}])
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "perm-1", "scopes": ["slack:*"]}]
    )

    row = upsert_agent_tool_permission(
        client,
        "org-1",
        "agent-1",
        connector_id=None,
        connector_type="slack",
        scopes=["slack:*"],
    )
    assert row["scopes"] == ["slack:*"]
    client.table.return_value.update.assert_called_once()


def test_invoke_denies_agent_without_permission(tool_ctx: ToolContext):
    from unittest.mock import patch

    tool_ctx.client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=[])
    )
    with patch("app.services.tool_service.write_audit_event"):
        result = invoke_tool(tool_ctx, "slack.post_message", {"channel": "#x", "message": "hi"})
    assert result.success is False
    assert result.error_code == "permission_denied"
