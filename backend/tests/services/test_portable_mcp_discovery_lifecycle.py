from app.services.mcp_client_service import (
    resolve_discovered_mcp_tool_enabled,
    should_enable_discovered_mcp_tool,
    stale_package_mcp_tool_ids,
)


def test_new_package_managed_mcp_tool_is_discovered_disabled() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    assert should_enable_discovered_mcp_tool(server, None) is False
    assert (
        resolve_discovered_mcp_tool_enabled(
            server,
            existing_enabled=None,
            enable_discovered_tools=None,
        )
        is False
    )


def test_rediscovery_preserves_reviewed_enabled_state_for_package_tool() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    assert (
        resolve_discovered_mcp_tool_enabled(
            server,
            existing_enabled=True,
            enable_discovered_tools=None,
        )
        is True
    )
    assert (
        resolve_discovered_mcp_tool_enabled(
            server,
            existing_enabled=False,
            enable_discovered_tools=None,
        )
        is False
    )


def test_explicit_discovery_override_can_reset_package_tool_state() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    assert (
        resolve_discovered_mcp_tool_enabled(
            server,
            existing_enabled=True,
            enable_discovered_tools=False,
        )
        is False
    )


def test_manual_mcp_discovery_keeps_legacy_auto_enable() -> None:
    assert should_enable_discovered_mcp_tool({}, None) is True


def test_disappeared_enabled_package_tool_is_marked_stale() -> None:
    rows = [
        {"id": "tool-a", "tool_name": "read_a", "enabled": True},
        {"id": "tool-b", "tool_name": "read_b", "enabled": False},
        {"id": "tool-c", "tool_name": "read_c", "enabled": True},
    ]
    assert stale_package_mcp_tool_ids(rows, {"read_a"}) == ["tool-c"]
