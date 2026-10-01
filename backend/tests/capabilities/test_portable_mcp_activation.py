import pytest

from app.capabilities.mcp_activation import declared_mcp_dependencies


def test_remote_https_dependency_is_preparable_but_stdio_is_not() -> None:
    rows = declared_mcp_dependencies(
        {
            "mcpServers": {
                "remote": {"url": "https://mcp.example.com/sse", "transport": "sse"},
                "local": {"command": "node", "transport": "stdio"},
            }
        }
    )
    by_name = {row["name"]: row for row in rows}
    assert by_name["remote"]["registrationAllowed"] is True
    assert by_name["local"]["registrationAllowed"] is False


@pytest.mark.parametrize(
    "url",
    [
        "http://mcp.example.com",
        "https://localhost/mcp",
        "https://127.0.0.1/mcp",
        "https://10.1.2.3/mcp",
        "https://user:pass@mcp.example.com/mcp",
    ],
)
def test_unsafe_remote_mcp_dependencies_are_blocked(url: str) -> None:
    [row] = declared_mcp_dependencies({"mcpServers": {"unsafe": {"url": url, "transport": "http"}}})
    assert row["registrationAllowed"] is False
    assert row["blockedReason"]


def test_remote_dependency_does_not_copy_package_credentials() -> None:
    [row] = declared_mcp_dependencies(
        {
            "mcpServers": {
                "remote": {
                    "url": "https://mcp.example.com/mcp",
                    "transport": "http",
                    "auth": {"type": "bearer", "token": "do-not-copy"},
                }
            }
        }
    )
    assert row["authType"] == "bearer"
    assert "token" not in row
