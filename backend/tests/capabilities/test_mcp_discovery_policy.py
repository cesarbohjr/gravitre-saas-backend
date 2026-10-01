from app.services.mcp_client_service import resolve_discovered_mcp_tool_enabled, should_enable_discovered_mcp_tool


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


def test_package_rediscovery_preserves_prior_enabled_state() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    assert resolve_discovered_mcp_tool_enabled(
        server,
        existing_enabled=True,
        enable_discovered_tools=None,
    ) is True
    assert resolve_discovered_mcp_tool_enabled(
        server,
        existing_enabled=False,
        enable_discovered_tools=None,
    ) is False


def test_new_package_tool_discovery_stays_inert_until_reviewed() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    assert resolve_discovered_mcp_tool_enabled(
        server,
        existing_enabled=None,
        enable_discovered_tools=None,
    ) is False


def test_explicit_rediscovery_policy_can_override_prior_review_state() -> None:
    server = {"source_capability_package_id": "pkg-1"}
    assert resolve_discovered_mcp_tool_enabled(
        server,
        existing_enabled=True,
        enable_discovered_tools=False,
    ) is False
