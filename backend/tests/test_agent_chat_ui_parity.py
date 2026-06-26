"""Agent chat UI tool list parity with agent jobs / backend mode config."""
from __future__ import annotations

from app.operators.assistant_mode_config import resolve_assistant_tool_names


def test_agent_chat_tool_list_matches_agent_jobs():
    agent_chat_tools = [
        "knowledge_base",
        "agent_status",
        "connector_status",
        "workflow_runs",
        "search_web",
    ]
    agent_mode_tools = resolve_assistant_tool_names("agent", None)
    for tool in agent_chat_tools:
        assert tool in agent_mode_tools
