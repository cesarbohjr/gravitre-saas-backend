import pytest

from app.services.mcp_client_service import should_enable_discovered_mcp_tool


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
