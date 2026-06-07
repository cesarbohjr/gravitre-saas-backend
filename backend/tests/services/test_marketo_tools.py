from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.marketo_tools import TOOL_EXECUTORS
from app.services.tool_types import ToolContext


def test_marketo_tool_executors_registered():
    assert "marketo.leads.get" in TOOL_EXECUTORS
    assert "marketo.leads.update" in TOOL_EXECUTORS
    assert "marketo.campaigns.list" in TOOL_EXECUTORS
    assert "marketo.programs.status" in TOOL_EXECUTORS
    assert "marketo.lists.add_to_static_list" in TOOL_EXECUTORS


def test_marketo_leads_get_success():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32)
    ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-mkt",
        environment_name="production",
    )
    conn = {"id": "mk-conn", "type": "marketo", "status": "active", "environment": "production", "config": {}}
    with patch("app.services.marketo_tools.get_connector_by_type", return_value=conn):
        with patch("app.services.marketo_tools.enforce_rate_limit"):
            with patch(
                "app.services.marketo_tools.ensure_marketo_session",
                return_value=("token", "abc-123", None),
            ):
                with patch("app.services.marketo_tools.get_lead", return_value={"result": [{"id": 9}]}):
                    result = TOOL_EXECUTORS["marketo.leads.get"](ctx, {"email": "a@b.com"})
    assert result.success is True
    assert result.data["result"][0]["id"] == 9
