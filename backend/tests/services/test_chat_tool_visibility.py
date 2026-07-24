"""Tests for unified chat tool visibility."""
from __future__ import annotations

from app.services.agent_platform_optimizer import narrow_tools_for_turn
from app.services.chat_tool_visibility import chat_visible_connector_tool_names
from app.operators.assistant_mode_config import resolve_assistant_tool_names


def _tool(name: str, write: bool = False) -> dict:
    return {
        "type": "function",
        "function": {"name": name, "description": "demo", "parameters": {"type": "object", "properties": {}}},
        "capability_tier": "write" if write else "read",
    }


def test_connected_integrations_keep_tool_coverage_when_unmentioned():
    tools = [
        _tool("assistant_connector_status"),
        _tool("gmail_messages_send", write=True),
        _tool("gmail_messages_list"),
        _tool("slack_post_message", write=True),
    ]
    visible, stats = narrow_tools_for_turn(
        tools,
        query="post a quick update",
        connected_integrations=["gmail", "slack"],
        requires_action=True,
        max_tools=4,
    )
    names = {row["function"]["name"] for row in visible}
    assert "gmail_messages_send" in names or "gmail_messages_list" in names
    assert "slack_post_message" in names
    assert "gmail" in stats.get("focusedConnectors", [])


def test_fast_mode_expands_when_connectors_live():
    bare = resolve_assistant_tool_names("fast", None)
    assert "workflow_runs" not in bare
    assert "search_web" not in bare

    connected = resolve_assistant_tool_names("fast", None, ["gmail", "hubspot"])
    assert "workflow_runs" in connected
    assert "search_web" in connected
    assert "connector_status" in connected


def test_chat_visible_tool_names_include_gmail_when_connected():
    names = chat_visible_connector_tool_names(connected_integrations=["gmail"])
    assert any(name.startswith("gmail_") for name in names)
