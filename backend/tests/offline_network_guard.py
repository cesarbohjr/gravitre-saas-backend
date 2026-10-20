"""Opt-in pytest plugin: -p tests.offline_network_guard.

Unit and simulated pipeline runs must fail rather than call real providers.
Do not enable this plugin for explicitly authorized live acceptance tests.
"""
import socket

import pytest


@pytest.fixture(autouse=True)
def prohibit_outbound_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise OSError("Offline verification: outbound network is disabled")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)

    # SDKs can dispatch through HTTP transports or C-backed gRPC without going
    # through Python's socket methods. Block those entry points as well, before
    # any provider receives a payload. ASGI/Mock transports stay available.
    import httpx
    import requests

    async def async_blocked(*args, **kwargs):
        raise OSError("Offline verification: outbound network is disabled")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_blocked)
    monkeypatch.setattr(requests.Session, "send", blocked)
    try:
        import grpc
    except ImportError:
        grpc = None
    if grpc is not None:
        for module in (grpc, grpc.aio):
            monkeypatch.setattr(module, "secure_channel", blocked)
            monkeypatch.setattr(module, "insecure_channel", blocked)
