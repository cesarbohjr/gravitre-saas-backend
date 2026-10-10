"""Shared Supabase clients must not multiplex one HTTP/2 connection across threads."""
from __future__ import annotations

import httpx

from app.core import db


def test_shared_http_options_use_http1_pool() -> None:
    http = db.shared_http_options().httpx_client
    assert isinstance(http, httpx.Client)
    assert http._transport._pool._http2 is False  # noqa: SLF001
    assert http._transport._pool._http1 is True  # noqa: SLF001


def test_shared_service_client_is_built_with_http1(monkeypatch) -> None:
    db.clear_shared_service_clients()
    seen: dict = {}

    def _create(url, key, options=None):
        seen["options"] = options
        return object()

    monkeypatch.setattr(db, "create_client", _create)
    monkeypatch.setattr(db.supabase, "create_client", _create)
    settings = type("S", (), {"supabase_url": "https://x.supabase.co", "supabase_service_role_key": "k"})()
    try:
        db.shared_service_client(settings, _create)
    finally:
        db.clear_shared_service_clients()
    assert seen["options"].httpx_client._transport._pool._http2 is False  # noqa: SLF001
