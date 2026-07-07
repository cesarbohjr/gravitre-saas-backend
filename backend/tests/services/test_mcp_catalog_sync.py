"""MCP catalog sync tests."""
from __future__ import annotations

from app.connectors.action_catalog.registry import get_vendor_catalog
from app.services.mcp_catalog_sync import build_mcp_vendor_catalog, sync_mcp_server_to_catalog


def test_build_mcp_vendor_catalog_splits_read_write():
    vendor, spec = build_mcp_vendor_catalog(
        server_name="Acme CRM",
        server_id="srv-1",
        tools=[
            {"tool_name": "get_leads", "tool_description": "List leads", "capability_tier": "read"},
            {"tool_name": "create_lead", "tool_description": "Create lead", "capability_tier": "write"},
        ],
    )
    assert vendor.startswith("mcp_")
    assert len(spec.v1) == 1
    assert len(spec.v2) == 1


def test_sync_registers_extension_in_catalog():
    get_vendor_catalog.cache_clear()
    vendor = sync_mcp_server_to_catalog(
        server_name="Partner",
        server_id="srv-2",
        tools=[{"tool_name": "fetch", "capability_tier": "read"}],
    )
    catalog = get_vendor_catalog()
    assert vendor in catalog
    assert len(catalog[vendor].v1) == 1
