"""Opt-in pytest plugin: fail closed on non-loopback network attempts.

Use ``python -m pytest -p tests.offline_network ...`` for offline contracts.
The guard is installed before collection and records attempts even if runtime
code catches the socket exception. HTTP MockTransport and local test servers
remain usable. This never supplies or reads a provider credential.
"""
from __future__ import annotations

import ipaddress
import socket
import traceback
from unittest.mock import patch

import pytest

_attempts: list[str] = []
_attempt_stacks: list[str] = []
_patches: list = []
_getaddrinfo = socket.getaddrinfo
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex


def _loopback(host) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="replace")
    if host in {"localhost", None}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _assert_local(host) -> None:
    if not _loopback(host):
        _attempts.append(str(host))
        _attempt_stacks.append("".join(traceback.format_stack(limit=16)))
        raise AssertionError(f"Offline regression attempted external network: {host}")


def _guard_getaddrinfo(host, *args, **kwargs):
    _assert_local(host)
    return _getaddrinfo(host, *args, **kwargs)


def _guard_connect(sock, address):
    if sock.family in {socket.AF_INET, socket.AF_INET6}:
        _assert_local(address[0])
    return _connect(sock, address)


def _guard_connect_ex(sock, address):
    if sock.family in {socket.AF_INET, socket.AF_INET6}:
        _assert_local(address[0])
    return _connect_ex(sock, address)


def pytest_configure(config):
    import httpx
    import requests.adapters

    original_http = httpx.HTTPTransport.handle_request
    original_async_http = httpx.AsyncHTTPTransport.handle_async_request
    original_requests = requests.adapters.HTTPAdapter.send

    def http_guard(transport, request):
        _assert_local(request.url.host)
        return original_http(transport, request)

    async def async_http_guard(transport, request):
        _assert_local(request.url.host)
        return await original_async_http(transport, request)

    def requests_guard(adapter, request, *args, **kwargs):
        from urllib.parse import urlsplit
        _assert_local(urlsplit(request.url).hostname)
        return original_requests(adapter, request, *args, **kwargs)

    # Guard before proxy resolution too: a loopback SOCKS/HTTP proxy must not
    # turn an external provider request into an apparently local socket.
    for target, replacement in (
        ("socket.getaddrinfo", _guard_getaddrinfo),
        ("socket.socket.connect", _guard_connect),
        ("socket.socket.connect_ex", _guard_connect_ex),
        ("httpx.HTTPTransport.handle_request", http_guard),
        ("httpx.AsyncHTTPTransport.handle_async_request", async_http_guard),
        ("requests.adapters.HTTPAdapter.send", requests_guard),
    ):
        guard = patch(target, replacement)
        guard.start()
        _patches.append(guard)
    # Google's legacy SDK uses gRPC C sockets, outside Python's socket hooks.
    # Deny external channel creation before any RPC/auth metadata is sent.
    import grpc
    import grpc.aio

    for module in (grpc, grpc.aio):
        for name in ("secure_channel", "insecure_channel"):
            original = getattr(module, name)
            def grpc_guard(target, *args, _original=original, **kwargs):
                text = target.decode() if isinstance(target, bytes) else str(target)
                host = text.removeprefix("dns:///")
                host = host[1:host.index("]")] if host.startswith("[") else host.split(":", 1)[0]
                _assert_local(host)
                return _original(target, *args, **kwargs)
            guard = patch.object(module, name, grpc_guard)
            guard.start()
            _patches.append(guard)


@pytest.fixture(autouse=True)
def assert_no_external_network():
    start = len(_attempts)
    stack_start = len(_attempt_stacks)
    yield
    attempted = _attempts[start:]
    if attempted:
        stacks = "\n".join(dict.fromkeys(_attempt_stacks[stack_start:]))
        pytest.fail("Offline regression attempted external network: " + ", ".join(sorted(set(attempted))) + "\n" + stacks)


def pytest_unconfigure(config):
    for guard in reversed(_patches):
        guard.stop()
    _patches.clear()
