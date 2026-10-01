from app.services.mcp_client_service import should_enable_discovered_mcp_tool


def test_manual_mcp_discovery_keeps_legacy_auto_enable() -> None:
    assert should_enable_discovered_mcp_tool({}, None) is True


def test_portable_mcp_discovery_defaults_inert() -> None:
    assert (
        should_enable_discovered_mcp_tool(
            {"source_capability_package_id": "pkg-1"},
            None,
        )
        is False
    )


def test_explicit_discovery_policy_wins() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    assert should_enable_discovered_mcp_tool(server, False) is False
    assert should_enable_discovered_mcp_tool(server, True) is True
