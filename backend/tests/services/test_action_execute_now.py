"""CAN_THIS_ACTION_EXECUTE_NOW — attach gate before tool_choice."""
from __future__ import annotations

from app.capability_ontology.tool_bridge import capability_tool_name
from app.services.action_execute_now import (
    CAN_THIS_ACTION_EXECUTE_NOW,
    can_this_action_execute_now,
    filter_tools_executable_now,
    unavailable_vendors_from_org_context,
)
from app.services.agent_platform_optimizer import narrow_tools_for_turn
from app.services.tool_router import narrow_permitted_tools_for_capability


def _tool(name: str, integration: str = "", write: bool = False) -> dict:
    return {
        "type": "function",
        "function": {"name": name, "description": "demo", "parameters": {"type": "object", "properties": {}}},
        "integration": integration,
        "capability_tier": "write" if write else "read",
    }


def test_named_alias_matches_function() -> None:
    assert CAN_THIS_ACTION_EXECUTE_NOW is can_this_action_execute_now


def test_platform_tools_always_executable() -> None:
    result = can_this_action_execute_now(
        tool_name="assistant_connector_status",
        connected_integrations=[],
    )
    assert result.ok is True
    assert result.reason == "always_executable"


def test_disconnected_vendor_is_not_executable() -> None:
    result = can_this_action_execute_now(
        tool_name="hubspot_search_contacts",
        connected_integrations=["gmail"],
    )
    assert result.ok is False
    assert result.reason == "not_connected"
    assert result.vendor == "hubspot"


def test_google_analytics_alias_matches_short_prefix() -> None:
    result = can_this_action_execute_now(
        tool_name="analytics_reports_run",
        connected_integrations=["google_analytics"],
    )
    assert result.ok is True
    assert result.reason == "executable"


def test_unavailable_vendor_blocks_even_when_listed_connected() -> None:
    result = can_this_action_execute_now(
        tool_name="hubspot_search_contacts",
        connected_integrations=["hubspot"],
        unavailable_vendors=["hubspot"],
    )
    assert result.ok is False
    assert result.reason == "vendor_unavailable"


def test_availability_by_vendor_false_blocks() -> None:
    result = can_this_action_execute_now(
        action_key="slack.chat.postMessage",
        connected_integrations=["slack"],
        availability_by_vendor={"slack": False},
    )
    assert result.ok is False
    assert result.reason == "execution_unavailable"


def test_org_context_unavailable_vendors() -> None:
    vendors = unavailable_vendors_from_org_context(
        {
            "integrations": [
                {"type": "hubspot", "executionAvailable": False},
                {"type": "gmail", "executionAvailable": True},
            ]
        }
    )
    assert vendors == ["hubspot"]


def test_narrow_drops_mentioned_disconnected_vendor() -> None:
    tools = [
        _tool("assistant_connector_status"),
        _tool("hubspot_search_contacts", "hubspot"),
        _tool("hubspot_create_contact", "hubspot", write=True),
        _tool("gmail_messages_list", "gmail"),
    ]
    visible, stats = narrow_tools_for_turn(
        tools,
        query="Create a HubSpot contact for Jane",
        connected_integrations=["gmail"],
        requires_action=True,
    )
    names = {row["function"]["name"] for row in visible}
    assert "hubspot_create_contact" not in names
    assert "hubspot_search_contacts" not in names
    assert "assistant_connector_status" in names
    assert stats.get("executeNowDropped", 0) >= 1


def test_filter_keeps_capability_tools() -> None:
    cap = capability_tool_name("crm.contact.create")
    kept, stats = filter_tools_executable_now(
        [_tool(cap, "capability"), _tool("hubspot_contacts_create", "hubspot")],
        connected_integrations=["gmail"],
    )
    names = {row["function"]["name"] for row in kept}
    assert cap in names
    assert "hubspot_contacts_create" not in names
    assert stats["executeNowDropped"] == 1


def test_tool_router_drops_disconnected_names() -> None:
    scoped, meta = narrow_permitted_tools_for_capability(
        ["hubspot.contacts.search", "web_search", "gmail.messages.list"],
        classification={},
        connected_integrations=["gmail"],
    )
    assert "hubspot.contacts.search" not in scoped
    assert "web_search" in scoped
    assert "gmail.messages.list" in scoped
    assert meta.get("executeNowDropped", 0) >= 1
