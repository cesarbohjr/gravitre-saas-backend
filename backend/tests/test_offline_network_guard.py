"""Prove the offline gate blocks providers before transport/proxy dispatch."""
import httpx
import pytest

from tests import offline_network


@pytest.mark.parametrize("url", ["https://api.openai.com/v1/responses", "https://generativelanguage.googleapis.com/v1/models"])
async def test_provider_transport_is_blocked_before_proxy_or_socket(monkeypatch, url):
    # An isolated recorder keeps intentional guard self-tests separate from
    # the plugin's per-test check for accidental network activity.
    attempts = []
    monkeypatch.setattr(offline_network, "_attempts", attempts)
    # Self-tests also work without -p by installing/restoring this plugin here.
    own_guard = not offline_network._patches
    if own_guard:
        offline_network.pytest_configure(None)
    try:
        client = httpx.AsyncClient(proxy="http://127.0.0.1:9999")
        with pytest.raises(AssertionError, match="external network"):
            await client.get(url)
        await client.aclose()
        assert attempts == [httpx.URL(url).host]
    finally:
        if own_guard:
            offline_network.pytest_unconfigure(None)


async def test_mock_transport_remains_available_without_real_network(monkeypatch):
    attempts = []
    monkeypatch.setattr(offline_network, "_attempts", attempts)
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={"synthetic": True}))
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get("https://api.openai.com/v1/responses")
    assert response.json() == {"synthetic": True}
    assert attempts == []


def test_google_grpc_channel_is_blocked_before_credentials_or_rpc(monkeypatch):
    import grpc

    attempts = []
    monkeypatch.setattr(offline_network, "_attempts", attempts)
    own_guard = not offline_network._patches
    if own_guard:
        offline_network.pytest_configure(None)
    try:
        with pytest.raises(AssertionError, match="external network"):
            grpc.secure_channel("generativelanguage.googleapis.com:443", grpc.ssl_channel_credentials())
        assert attempts == ["generativelanguage.googleapis.com"]
    finally:
        if own_guard:
            offline_network.pytest_unconfigure(None)
