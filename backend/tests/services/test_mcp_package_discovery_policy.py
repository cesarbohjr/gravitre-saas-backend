import pytest

from app.services.mcp_client_service import catalog_visible_mcp_tools, should_enable_discovered_mcp_tool, stale_package_mcp_tool_ids


def test_new_portable_package_tools_default_disabled() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    assert should_enable_discovered_mcp_tool(server, None) is False


def test_manual_mcp_tools_keep_legacy_auto_enable() -> None:
    server = {"source_capability_package_id": None}
    assert should_enable_discovered_mcp_tool(server, None) is True


def test_explicit_discovery_override_wins() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    assert should_enable_discovered_mcp_tool(server, True) is True
    assert should_enable_discovered_mcp_tool(server, False) is False


def test_portable_package_catalog_exposes_only_admin_enabled_tools() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    tools = [
        {"id": "new", "enabled": False},
        {"id": "approved", "enabled": True},
    ]
    assert catalog_visible_mcp_tools(server, tools) == [{"id": "approved", "enabled": True}]


def test_manual_mcp_catalog_behavior_is_unchanged() -> None:
    server = {"source_capability_package_id": None}
    tools = [{"id": "a", "enabled": False}, {"id": "b", "enabled": True}]
    assert catalog_visible_mcp_tools(server, tools) is tools


def test_removed_remote_tool_is_marked_stale_only_when_previously_enabled() -> None:
    persisted = [
        {"id": "keep", "tool_name": "lookup", "enabled": True},
        {"id": "removed-enabled", "tool_name": "create", "enabled": True},
        {"id": "removed-disabled", "tool_name": "delete", "enabled": False},
    ]
    assert stale_package_mcp_tool_ids(persisted, {"lookup"}) == ["removed-enabled"]
