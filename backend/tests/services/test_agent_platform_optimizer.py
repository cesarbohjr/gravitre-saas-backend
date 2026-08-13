"""Tests for agent platform performance optimizations."""
from __future__ import annotations

from app.services.agent_platform_optimizer import (
    compress_tool_definitions,
    narrow_tools_for_turn,
)
from app.services.connector_snapshot_cache import (
    get_cached_connected,
    set_cached_connected,
)
from app.services.read_action_result_cache import (
    get_cached_read_result,
    is_read_invoke_action,
    set_cached_read_result,
)


def _tool(name: str, integration: str = "", write: bool = False) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "x" * 200,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10},
                },
            },
        },
        "capability_tier": "write" if write else "read",
    }


def test_narrow_tools_connected_coverage_does_not_crash_on_hello():
    """Regression: _ensure_connected_tool_coverage must receive query (ec47ff03 NameError)."""
    tools = [
        _tool("assistant_connector_status"),
        _tool("hubspot_search_contacts"),
        _tool("gmail_messages_send", write=True),
        _tool("gmail_messages_batch", write=True),
        _tool("apollo_search_people"),
    ]
    visible, stats = narrow_tools_for_turn(
        tools,
        query="hello",
        connected_integrations=["gmail", "hubspot", "apollo"],
        requires_action=False,
    )
    names = {row["function"]["name"] for row in visible}
    assert stats["visibleTools"] >= 2
    assert "hubspot_search_contacts" in names or "apollo_search_people" in names


def test_narrow_tools_focuses_on_mentioned_connector():
    tools = [
        _tool("assistant_connector_status"),
        _tool("hubspot_search_contacts"),
        _tool("hubspot_create_contact", write=True),
        _tool("slack_post_message", write=True),
        _tool("apollo_search_people"),
    ]
    visible, stats = narrow_tools_for_turn(
        tools,
        query="Create a HubSpot contact for Jane",
        connected_integrations=["hubspot", "slack", "apollo"],
        requires_action=True,
    )
    names = {row["function"]["name"] for row in visible}
    assert "hubspot_create_contact" in names
    assert "hubspot_search_contacts" in names
    # Connected coverage keeps one Slack tool even when HubSpot is the focus.
    injected = int(stats.get("capabilityToolsInjected") or 0)
    assert stats["visibleTools"] <= stats["totalTools"] + injected


def test_compress_tool_definitions_trims_descriptions():
    tools = [_tool("hubspot_search_contacts")]
    compressed = compress_tool_definitions(tools)
    desc = compressed[0]["function"]["description"]
    assert len(desc) <= 141
    assert "properties" in compressed[0]["function"]["parameters"]
    assert "description" not in compressed[0]["function"]["parameters"]["properties"]["query"]


def test_connector_snapshot_cache_roundtrip():
    set_cached_connected("org-1", ["hubspot", "slack"], environment_name="production", ttl_seconds=60)
    assert get_cached_connected("org-1", "production") == ["hubspot", "slack"]


def test_read_action_cache_and_classifier():
    assert is_read_invoke_action("hubspot.contacts.search")
    assert not is_read_invoke_action("hubspot.contacts.create")
    payload = {"success": True, "result": {"rows": []}}
    set_cached_read_result("org-1", "hubspot.contacts.search", {"query": "jane"}, payload)
    cached = get_cached_read_result("org-1", "hubspot.contacts.search", {"query": "jane"})
    assert cached == payload
