"""Acme Tools demo partner handler tests."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.connectors.partners.acme_tools_demo import ensure_acme_tools_demo_registered
from app.connectors.sdk import clear_partner_registry, list_partner_actions
from app.services.tool_service import invoke_tool
from app.services.tool_types import ToolContext


def setup_function():
    clear_partner_registry()


def teardown_function():
    clear_partner_registry()


def test_register_acme_demo_handlers():
    ensure_acme_tools_demo_registered()
    actions = list_partner_actions()
    assert "acme_tools.tickets.list" in actions
    assert "acme_tools.tickets.create" in actions


def test_invoke_acme_tickets_list():
    ensure_acme_tools_demo_registered()
    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=None,
        org_id="org-1",
        actor_id="user-1",
    )
    with patch("app.services.tool_service._write_tool_audit"), patch(
        "app.services.tool_service.assert_agent_tool_permission"
    ):
        result = invoke_tool(ctx, "acme_tools.tickets.list", {"status": "open", "limit": 5})
    assert result.success is True
    assert len(result.data["tickets"]) >= 1
