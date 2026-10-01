from app.capabilities.mcp_activation import declared_mcp_dependencies
from app.routers.mcp_admin import _normalize_mcp_transport
from app.services.mcp_client_service import _streamable_http_client


def test_streamable_http_dependency_normalizes_hyphenated_alias() -> None:
    [row] = declared_mcp_dependencies(
        {
            "mcpServers": {
                "remote": {
                    "url": "https://mcp.example.com/mcp",
                    "transport": "streamable-http",
                }
            }
        }
    )
    assert row["transport"] == "streamable_http"
    assert row["registrationAllowed"] is True


def test_admin_mcp_transport_normalization_supports_streamable_http() -> None:
    assert _normalize_mcp_transport("streamable-http") == "streamable_http"
    assert _normalize_mcp_transport("streamablehttp") == "streamable_http"


def test_streamable_http_client_factory_resolves_installed_mcp_sdk() -> None:
    assert callable(_streamable_http_client())
