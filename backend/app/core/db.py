"""Canonical Supabase (service-role) client factory.

Lives in app.core so the AI core and other layers don't have to import it from
app.workflows. Returns a service-role client (bypasses RLS) for backend writes.

Perf (2026-10-08): the factories used to build a brand-new client per call, so
every request paid a fresh TCP + TLS handshake to Supabase through its own
httpx pool (and those pools were never closed). One client per (url, key) is
now shared process-wide, the same pattern app/auth/dependencies.py has used
since 2026-09-07: supabase-py's sync Client wraps httpx.Client, which is safe
for concurrent use, and the service-role credentials are static.
"""
from __future__ import annotations

import threading
from collections.abc import Callable

import httpx
import supabase
from supabase import Client, ClientOptions, create_client

from app.config import Settings

_shared_clients: dict[tuple[str, str], Client] = {}
_shared_lock = threading.Lock()


# supabase-py's REST, auth and storage clients open HTTP/2 connections by
# default. One HTTP/2 connection multiplexed across the threadpool that runs
# sync endpoints fails intermittently with
# ``httpx.ReadError: [Errno 11] Resource temporarily unavailable`` (seen in
# production right after deploys on POST /api/conversations). A shared
# HTTP/1.1 pool is thread-safe and gives each concurrent request its own
# connection.
_SHARED_HTTP_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
_SHARED_HTTP_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30.0)


def shared_http_options() -> ClientOptions:
    """Client options for a long-lived, thread-shared service client."""
    http = httpx.Client(
        http2=False,
        timeout=_SHARED_HTTP_TIMEOUT,
        follow_redirects=True,
        # A custom transport ignores the client's own limits/http2 arguments,
        # so the pool settings go on the transport itself.
        transport=httpx.HTTPTransport(retries=2, http2=False, limits=_SHARED_HTTP_LIMITS),
    )
    return ClientOptions(httpx_client=http)


def shared_service_client(
    settings: Settings,
    factory: Callable[[str, str], Client] | None = None,
) -> Client:
    """Process-wide service-role client for ``settings``.

    ``factory`` is the caller module's own ``create_client`` binding. When a test
    has patched it (or ``supabase.create_client``) the patched factory is called
    directly and nothing is cached, so mocks never leak between tests.
    """
    factory = factory or create_client
    real = factory is create_client and supabase.create_client is create_client
    if not real:
        return factory(settings.supabase_url, settings.supabase_service_role_key)
    key = (settings.supabase_url, settings.supabase_service_role_key)
    client = _shared_clients.get(key)
    if client is None:
        with _shared_lock:
            client = _shared_clients.get(key)
            if client is None:
                client = create_client(*key, options=shared_http_options())
                _shared_clients[key] = client
    return client


def clear_shared_service_clients() -> None:
    """Test-only: drop cached clients."""
    with _shared_lock:
        _shared_clients.clear()


def get_supabase_client(settings: Settings) -> Client:
    return shared_service_client(settings, create_client)


def is_shared_service_client(client: object) -> bool:
    """True for a process-wide client from ``shared_service_client``.

    Lets read-through caches apply only in production, never to per-test mock
    clients (whose ids can be reused once garbage collected).
    """
    return any(client is cached for cached in _shared_clients.values())
