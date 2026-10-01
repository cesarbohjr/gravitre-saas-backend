from app.capabilities.mcp_activation import declared_mcp_dependencies


def test_remote_https_mcp_dependency_can_be_prepared() -> None:
    rows = declared_mcp_dependencies(
        {"mcpServers": {"crm": {"url": "https://mcp.example.com", "transport": "http"}}}
    )
    assert rows[0]["registrationAllowed"] is True


def test_stdio_mcp_dependency_is_not_auto_registered() -> None:
    rows = declared_mcp_dependencies(
        {"mcpServers": {"local": {"command": "node", "args": ["server.js"], "transport": "stdio"}}}
    )
    assert rows[0]["registrationAllowed"] is False
    assert "local/stdio" in rows[0]["blockedReason"]
