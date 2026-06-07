from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.connector_tool_auth import resolve_github_access_token, resolve_zendesk_auth
from app.services.tool_service import invoke_tool
from app.services.tool_types import ToolContext


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


def test_resolve_github_prefers_oauth():
    with patch("app.connectors.connector_tool_auth.ensure_generic_session", return_value=("gho_oauth", None)):
        token = resolve_github_access_token(MagicMock(), "org-1", "gh-1", MagicMock())
    assert token == "gho_oauth"


def test_resolve_github_falls_back_to_pat():
    with patch("app.connectors.connector_tool_auth.ensure_generic_session", return_value=(None, "err")):
        with patch("app.connectors.connector_tool_auth.load_oauth_tokens", return_value=None):
            with patch("app.connectors.connector_tool_auth.get_decrypted_secret", return_value="ghp_pat"):
                token = resolve_github_access_token(MagicMock(), "org-1", "gh-1", MagicMock())
    assert token == "ghp_pat"


def test_resolve_zendesk_oauth_path():
    conn = {"id": "zd-1", "config": {"subdomain": "acme"}}
    with patch("app.connectors.connector_tool_auth.ensure_generic_session", return_value=("zd_oauth", None)):
        sub, email, api, oauth = resolve_zendesk_auth(MagicMock(), "org-1", conn, MagicMock())
    assert sub == "acme"
    assert oauth == "zd_oauth"
    assert email is None and api is None


def test_zendesk_create_with_oauth_token(tool_ctx: ToolContext):
    conn = {"id": "zd-1", "type": "zendesk", "config": {"subdomain": "acme"}, "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch(
                "app.connectors.connector_tool_auth.ensure_generic_session",
                return_value=("oauth-token", None),
            ):
                with patch(
                    "app.services.tool_service.create_ticket",
                    return_value={"id": 42, "subject": "Help"},
                ) as create_mock:
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
    create_mock.assert_called_once()
    assert create_mock.call_args.kwargs.get("oauth_access_token") == "oauth-token"


def test_github_list_prs_with_oauth(tool_ctx: ToolContext):
    conn = {"id": "gh-1", "type": "github", "config": {"owner": "o", "repo": "r"}, "environment": "production"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.get_connector", return_value=conn):
            with patch("app.services.tool_service.enforce_rate_limit"):
                with patch(
                    "app.connectors.connector_tool_auth.ensure_generic_session",
                    return_value=("gho_token", None),
                ):
                    with patch(
                        "app.services.tool_service.list_pull_requests",
                        return_value=[{"number": 1}],
                    ) as list_mock:
                        with patch("app.services.tool_service.write_audit_event"):
                            with patch(
                                "app.services.agent_tool_permissions.list_agent_tool_permissions",
                                return_value=[{"connector_type": "github", "scopes": ["github:*"], "expires_at": None}],
                            ):
                                result = invoke_tool(
                                    tool_ctx,
                                    "github.pulls.list",
                                    {"owner": "o", "repo": "r"},
                                )
    assert result.success is True
    list_mock.assert_called_once()
    assert list_mock.call_args.args[0] == "gho_token"
