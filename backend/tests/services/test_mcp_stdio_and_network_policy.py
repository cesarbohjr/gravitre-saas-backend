"""Tenant-created MCP servers cannot launch backend processes or reach private networks.

Release 1 gate: an org admin cannot start a process on the backend host through
an MCP server, and an admin-added remote server cannot point at loopback,
private, link-local or reserved addresses unless the operator opts in.
"""
from __future__ import annotations

import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_org_context, require_admin
from app.config import get_settings
from app.routers import mcp_admin
from app.services.mcp_client_service import (
    MCPClientService,
    MCPTransportNotAllowedError,
    _validate_mcp_runtime_endpoint,
)

ORG = "11111111-1111-4111-8111-111111111111"


def _settings(**overrides):
    base = {
        "connector_secrets_encryption_key": "k" * 64,
        "mcp_stdio_transport_enabled": False,
        "mcp_allow_private_network_servers": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _fake_dns(address: str):
    def fake_getaddrinfo(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    return fake_getaddrinfo


# ---------------------------------------------------------------- service layer


@pytest.mark.asyncio
async def test_stdio_discovery_never_spawns_a_process_by_default():
    service = MCPClientService(settings=_settings())
    server = {"id": "srv", "transport": "stdio", "server_url": "touch /tmp/pwned", "enabled": True}
    with patch("mcp.client.stdio.stdio_client") as spawn:
        with pytest.raises(MCPTransportNotAllowedError):
            await service._list_remote_tools(server)
        with pytest.raises(MCPTransportNotAllowedError):
            await service._call_mcp_server(server, "anything", {})
        # Direct calls to the stdio helpers are refused too.
        with pytest.raises(MCPTransportNotAllowedError):
            await service._list_tools_stdio(server)
        with pytest.raises(MCPTransportNotAllowedError):
            await service._call_stdio(server, "anything", {})
    spawn.assert_not_called()


@pytest.mark.asyncio
async def test_missing_transport_is_treated_as_stdio_and_refused():
    service = MCPClientService(settings=_settings())
    with pytest.raises(MCPTransportNotAllowedError):
        await service._list_remote_tools({"id": "srv", "server_url": "id"})


@pytest.mark.asyncio
async def test_operator_opt_in_reaches_stdio_helper():
    service = MCPClientService(settings=_settings(mcp_stdio_transport_enabled=True))
    with patch.object(service, "_list_tools_stdio", new=AsyncMock(return_value=[])) as helper:
        assert await service._list_remote_tools({"transport": "stdio", "server_url": "x"}) == []
    helper.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_refuses_stdio_before_sending_and_releases_approval():
    """A transport refusal happens before any request, so the approval stays reusable."""
    service = MCPClientService(settings=_settings())
    tool = {
        "id": "tool-1",
        "server_id": "srv",
        "tool_name": "create_record",
        "capability_tier": "write",
        "enabled": True,
    }
    server = {"id": "srv", "transport": "stdio", "server_url": "echo", "enabled": True}
    call = AsyncMock()
    with (
        patch.object(service, "_load_tool", new=AsyncMock(return_value=tool)),
        patch.object(service, "_verify_approval", new=AsyncMock(return_value="claim-1")),
        patch.object(service, "_load_server", new=AsyncMock(return_value=server)),
        patch.object(service, "_release_approval", new=AsyncMock()) as release,
        patch.object(service, "_call_mcp_server", new=call),
        patch.object(service, "_client", return_value=MagicMock()),
    ):
        with pytest.raises(MCPTransportNotAllowedError):
            await service.execute_tool("tool-1", ORG, {"a": 1}, approval_id="appr-1")
    call.assert_not_awaited()
    release.assert_awaited_once_with("appr-1", ORG, "claim-1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.1", "169.254.169.254", "0.0.0.0", "::1", "fd00::1"],
)
async def test_admin_server_resolving_to_private_space_is_refused(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns(address))
    with pytest.raises(ValueError, match="private or reserved"):
        await _validate_mcp_runtime_endpoint(
            {"source_capability_package_id": None, "server_url": "https://mcp.example.com/mcp"}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    ["http://localhost:3000", "http://127.0.0.1/mcp", "http://[::ffff:127.0.0.1]/mcp", "http://169.254.169.254/latest"],
)
async def test_admin_server_literal_private_hosts_are_refused(url):
    with pytest.raises(ValueError):
        await _validate_mcp_runtime_endpoint({"source_capability_package_id": None, "server_url": url})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    ["ftp://mcp.example.com", "file:///etc/passwd", "https://user:pw@mcp.example.com/mcp", "not a url"],
)
async def test_admin_server_bad_url_shapes_are_refused(url):
    with pytest.raises(ValueError):
        await _validate_mcp_runtime_endpoint({"source_capability_package_id": None, "server_url": url})


@pytest.mark.asyncio
async def test_admin_server_public_address_is_allowed(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns("93.184.216.34"))
    await _validate_mcp_runtime_endpoint(
        {"source_capability_package_id": None, "server_url": "https://mcp.example.com/mcp"}
    )


@pytest.mark.asyncio
async def test_private_network_opt_in_allows_internal_servers():
    await _validate_mcp_runtime_endpoint(
        {"source_capability_package_id": None, "server_url": "http://10.0.0.5:8080/mcp"},
        allow_private_network=True,
    )


@pytest.mark.asyncio
async def test_private_network_opt_in_does_not_relax_package_servers(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns("10.0.0.5"))
    with pytest.raises(ValueError, match="private or reserved"):
        await _validate_mcp_runtime_endpoint(
            {"source_capability_package_id": "pkg-1", "server_url": "https://mcp.example.com/mcp"},
            allow_private_network=True,
        )


@pytest.mark.asyncio
async def test_remote_calls_recheck_dns_before_each_use(monkeypatch):
    """DNS that flips to a private address after registration is caught at call time."""
    service = MCPClientService(settings=_settings())
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns("127.0.0.1"))
    server = {"transport": "streamable_http", "server_url": "https://mcp.example.com/mcp"}
    with pytest.raises(ValueError, match="private or reserved"):
        await service._call_mcp_server(server, "t", {})
    with pytest.raises(ValueError, match="private or reserved"):
        await service._list_remote_tools(server)


# ----------------------------------------------------------------- admin routes


class _Table:
    def __init__(self, store: dict, name: str):
        self.store, self.name = store, name
        self._row = None

    def insert(self, row):
        self.store.setdefault(self.name, []).append(row)
        self._row = row
        return self

    def select(self, *_a, **_k):
        return self

    def update(self, patch):
        self.store.setdefault("updates", []).append(patch)
        return self

    def eq(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        if self._row is not None:
            return SimpleNamespace(data=[self._row])
        return SimpleNamespace(data=self.store.get("select_rows", []))


class _Client:
    def __init__(self, store: dict):
        self.store = store

    def table(self, name):
        return _Table(self.store, name)


@pytest.fixture
def api(monkeypatch):
    store: dict = {}
    settings = _settings()
    app = FastAPI()
    app.include_router(mcp_admin.router)
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-1"}, ORG)
    app.dependency_overrides[get_org_context] = lambda: ORG
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(mcp_admin, "get_supabase_client", lambda _s: _Client(store))
    return TestClient(app), store, settings


def test_admin_cannot_create_stdio_server(api):
    client, store, _ = api
    resp = client.post(
        "/api/admin/mcp/servers",
        json={"serverName": "x", "serverUrl": "bash -c 'id'", "transport": "stdio"},
    )
    assert resp.status_code == 422
    assert "stdio" in resp.json()["detail"]
    assert "mcp_servers" not in store


def test_create_without_transport_no_longer_defaults_to_stdio(api, monkeypatch):
    client, store, _ = api
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns("93.184.216.34"))
    resp = client.post(
        "/api/admin/mcp/servers",
        json={"serverName": "x", "serverUrl": "https://mcp.example.com/mcp"},
    )
    assert resp.status_code == 200, resp.text
    assert store["mcp_servers"][0]["transport"] == "streamable_http"


def test_create_command_line_without_transport_is_refused(api):
    client, store, _ = api
    resp = client.post("/api/admin/mcp/servers", json={"serverName": "x", "serverUrl": "touch /tmp/x"})
    assert resp.status_code == 422
    assert "mcp_servers" not in store


def test_admin_cannot_create_server_on_private_network(api):
    client, store, _ = api
    resp = client.post(
        "/api/admin/mcp/servers",
        json={"serverName": "x", "serverUrl": "http://169.254.169.254/latest", "transport": "http"},
    )
    assert resp.status_code == 422
    assert "mcp_servers" not in store


def test_existing_stdio_row_cannot_be_enabled(api):
    client, store, _ = api
    store["select_rows"] = [{"id": "srv", "transport": "stdio", "source_capability_package_id": None}]
    resp = client.patch("/api/admin/mcp/servers/srv", json={"enabled": True})
    assert resp.status_code == 422
    assert "updates" not in store


def test_existing_stdio_row_discovery_is_refused_without_spawning(api, monkeypatch):
    client, store, settings = api
    store["select_rows"] = [{"id": "srv", "enabled": True, "source_capability_package_id": None}]
    service = MCPClientService(settings=settings)
    monkeypatch.setattr(mcp_admin, "get_mcp_client_service", lambda _s: service)
    monkeypatch.setattr(
        service,
        "_load_server",
        AsyncMock(return_value={"id": "srv", "transport": "stdio", "server_url": "touch /tmp/x"}),
    )
    with patch("mcp.client.stdio.stdio_client") as spawn:
        resp = client.post("/api/admin/mcp/servers/srv/discover")
    assert resp.status_code == 422
    spawn.assert_not_called()
