import socket

import pytest

from app.services.mcp_client_service import _validate_portable_mcp_runtime_endpoint


@pytest.mark.asyncio
async def test_portable_mcp_runtime_rejects_private_dns_resolution(monkeypatch) -> None:
    def fake_getaddrinfo(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ValueError, match="private or reserved"):
        await _validate_portable_mcp_runtime_endpoint(
            {
                "source_capability_package_id": "pkg-1",
                "server_url": "https://mcp.example.com/sse",
            }
        )


@pytest.mark.asyncio
async def test_manual_mcp_runtime_keeps_legacy_network_policy() -> None:
    await _validate_portable_mcp_runtime_endpoint(
        {
            "source_capability_package_id": None,
            "server_url": "http://localhost:3000",
        }
    )
