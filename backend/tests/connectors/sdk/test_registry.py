"""Partner connector registry tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.connectors.sdk import clear_partner_registry, list_partner_actions, parse_manifest
from app.connectors.sdk.registry import register_partner_connector
from app.services.agent_tool_permissions import ACTION_REQUIRED_SCOPES
from app.services.tool_service import invoke_tool
from app.services.tool_types import NormalizedResult, ToolContext, ToolNotFoundError


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_partner_registry()
    yield
    clear_partner_registry()


def _sample_manifest():
    return parse_manifest(
        {
            "manifestVersion": "1.0",
            "id": "com.acme.tools",
            "name": "Acme Tools",
            "version": "1.0.0",
            "vendor": "acme_tools",
            "auth": {"type": "apiKey"},
            "capabilities": ["actions"],
            "actions": [
                {
                    "id": "tickets.list",
                    "name": "List tickets",
                    "scopes": ["acme_tools:tickets:read"],
                }
            ],
        }
    )


def test_register_and_invoke_partner_action():
    manifest = _sample_manifest()

    def _list(ctx, params):
        return NormalizedResult(
            success=True,
            action="acme_tools.tickets.list",
            data={"tickets": [{"id": "1"}]},
        )

    register_partner_connector(manifest, {"tickets.list": _list})
    assert "acme_tools.tickets.list" in list_partner_actions()
    assert ACTION_REQUIRED_SCOPES["acme_tools.tickets.list"] == ["acme_tools:tickets:read"]

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=None,
        org_id="org-1",
        actor_id="user-1",
    )
    with patch("app.services.tool_service._write_tool_audit"), patch(
        "app.services.tool_service.assert_agent_tool_permission"
    ):
        result = invoke_tool(ctx, "acme_tools.tickets.list", {})
    assert result.success is True
    assert result.data["tickets"][0]["id"] == "1"


def test_missing_handler_raises():
    manifest = _sample_manifest()
    with pytest.raises(ValueError, match="no handler was provided"):
        register_partner_connector(manifest, {})


def test_unknown_action_still_raises():
    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=None,
        org_id="org-1",
        actor_id="user-1",
    )
    with pytest.raises(ToolNotFoundError):
        invoke_tool(ctx, "acme_tools.unknown.action", {})
