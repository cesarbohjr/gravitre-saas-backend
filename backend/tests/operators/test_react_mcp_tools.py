"""ReAct loop includes org MCP tools via get_available_tools."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.react_engine import ReActEngine, ReActStatus
from app.services.tool_types import ToolContext


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
        task_id="job-1",
    )


@pytest.mark.asyncio
async def test_react_uses_get_available_tools_including_mcp(tool_ctx: ToolContext):
    settings = SimpleNamespace(disable_ai=False, ai_pii_redaction_enabled=False)
    registry = MagicMock()
    registry.list_connected_integrations.return_value = ["hubspot"]
    registry.get_available_tools = AsyncMock(
        return_value=[
            {
                "type": "function",
                "function": {"name": "hubspot_contacts_search", "description": "search", "parameters": {}},
            },
            {
                "type": "function",
                "function": {"name": "mcp_partner_fetch", "description": "MCP", "parameters": {}},
            },
        ]
    )
    engine = ReActEngine(settings=settings, registry=registry)
    engine.router = MagicMock()
    engine.router._openai = AsyncMock()
    message = SimpleNamespace(content="Done", tool_calls=[])
    engine.router._openai.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])
    )
    with patch("app.operators.react_engine.moderate_input", new=AsyncMock()):
        with patch("app.operators.react_engine.write_audit_event"):
            result = await engine.run(
                ctx=tool_ctx,
                task="Fetch partner data",
                permitted_tools=["*"],
                connected_integrations=["hubspot"],
            )
    registry.get_available_tools.assert_awaited_once()
    assert result.status == ReActStatus.COMPLETED
