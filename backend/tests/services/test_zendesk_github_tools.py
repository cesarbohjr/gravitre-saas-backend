from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext, ToolValidationError


@pytest.fixture
def tool_ctx() -> ToolContext:
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32)
    return ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-cs",
        environment_name="production",
    )


def test_zendesk_and_github_actions_registered():
    actions = list_registered_actions()
    for action in (
        "zendesk.tickets.get",
        "zendesk.tickets.create",
        "zendesk.tickets.update",
        "zendesk.tickets.add_tags",
        "github.pulls.list",
        "github.issues.create",
        "github.issues.comment",
        "github.pulls.request_reviewer",
        "calendar.freebusy",
        "calendar.events.create",
    ):
        assert action in actions


def test_zendesk_create_ticket(tool_ctx: ToolContext):
    conn = {"id": "zd-1", "type": "zendesk", "config": {"subdomain": "acme"}, "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.connectors.connector_tool_auth.resolve_zendesk_auth",
                return_value=("acme", "a@b.com", "token", None),
            ):
                with patch(
                    "app.services.tool_service.create_ticket",
                    return_value={"id": 99, "subject": "Help"},
                ):
                    with patch("app.services.tool_service.write_audit_event"):
                        with patch(
                            "app.services.agent_tool_permissions.list_agent_tool_permissions",
                            return_value=[{"connector_type": "zendesk", "scopes": ["zendesk:*"], "expires_at": None}],
                        ):
                            result = invoke_tool(
                                tool_ctx,
                                "zendesk.tickets.create",
                                {"subject": "Help", "comment": "Body"},
                            )
    assert result.success is True
    assert result.data["ticket"]["id"] == 99


def test_github_list_prs_requires_owner_repo(tool_ctx: ToolContext):
    conn = {"id": "gh-1", "type": "github", "config": {}, "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.connectors.connector_tool_auth.resolve_github_access_token",
                return_value="ghp_test",
            ):
                with patch("app.services.tool_service.write_audit_event"):
                    with patch(
                        "app.services.agent_tool_permissions.list_agent_tool_permissions",
                        return_value=[{"connector_type": "github", "scopes": ["github:*"], "expires_at": None}],
                    ):
                        result = invoke_tool(tool_ctx, "github.pulls.list", {})
    assert result.success is False
