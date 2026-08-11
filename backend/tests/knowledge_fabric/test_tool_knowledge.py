"""Tool expertise packs — catalog attachment + connector-driven access."""
from __future__ import annotations

from app.connectors.action_catalog.integration_taxonomy import (
    get_integration_class,
    mcp_preference_for_vendor,
    tool_knowledge_pack_id,
)
from app.connectors.action_catalog.registry import get_vendor_spec
from app.knowledge_fabric.registry import PLATFORM_KNOWLEDGE_SOURCES, get_spec
from app.knowledge_fabric.tool_knowledge import (
    tool_knowledge_vendors,
    tool_packs_for_connected_vendors,
)


def test_tool_expertise_sources_are_licence_verified_original():
    specs = [s for s in PLATFORM_KNOWLEDGE_SOURCES if s.department == "tool_expertise"]
    assert specs
    for spec in specs:
        assert spec.licence_verified is True
        assert spec.commercial_use_allowed is True
        assert spec.license == "Gravitre-Original"
        assert spec.pack_id.startswith("pack.tool.")
        spec.validate()


def test_tool_packs_driven_by_connected_vendors_not_department():
    sales = tool_packs_for_connected_vendors(["hubspot"])
    marketing = tool_packs_for_connected_vendors(["hubspot"])
    assert sales == marketing == ["pack.tool.hubspot"]
    assert tool_packs_for_connected_vendors(["slack", "stripe"]) == [
        "pack.tool.slack",
        "pack.tool.stripe",
    ]
    assert tool_packs_for_connected_vendors(["shopify"]) == []  # missing connector


def test_hubspot_catalog_still_has_actions_alongside_tool_pack():
    assert "hubspot" in tool_knowledge_vendors()
    spec = get_vendor_spec("hubspot")
    assert spec is not None
    assert len(spec.all_actions()) >= 10
    assert get_spec("tool.hubspot.expertise") is not None
    assert tool_knowledge_pack_id("hubspot") == "pack.tool.hubspot"


def test_integration_class_and_mcp_preference():
    assert get_integration_class("hubspot") == "OPEN_API"
    assert get_integration_class("google_analytics") == "OPEN_API_CUSTOMER_ENTITLEMENT"
    assert get_integration_class("notion") == "MCP_AVAILABLE"
    pref = mcp_preference_for_vendor("notion")
    assert pref["prefer"] == "native_actionspec"
    payload = get_vendor_spec("notion").to_dict(implemented_tools=set())
    assert payload["integrationClass"] == "MCP_AVAILABLE"
    assert payload["mcpPreference"]["prefer"] == "native_actionspec"
