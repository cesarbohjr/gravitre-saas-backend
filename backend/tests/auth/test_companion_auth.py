from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.config import Settings, get_settings
from app.routers import companion_auth


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="secret",
        openai_api_key="sk-test",
        anthropic_api_key="sk-test",
        google_api_key="g",
    )


def _response(status: int, body: dict) -> MagicMock:
    res = MagicMock()
    res.status_code = status
    res.json.return_value = body
    return res


SESSION = {
    "access_token": "access-1",
    "refresh_token": "refresh-1",
    "expires_in": 3600,
    "expires_at": 1_900_000_000,
    "user": {"id": "user-1"},
}


@pytest.fixture
def app_client():
    app = FastAPI()
    app.include_router(companion_auth.router)
    app.dependency_overrides[get_settings] = _settings
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "cesar@example.com"}
    return TestClient(app), app


def _http_client(post_side_effect):
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.post.side_effect = post_side_effect
    return client


def test_companion_session_mints_a_separate_session(app_client):
    client, _ = app_client
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/admin/generate_link"):
            return _response(200, {"properties": {"hashed_token": "hash-1"}})
        return _response(200, SESSION)

    with patch.object(companion_auth.httpx, "Client", return_value=_http_client(post)):
        res = client.post("/api/auth/companion-session", json={"client": "desktop"})

    assert res.status_code == 200
    body = res.json()
    assert body["access_token"] == "access-1"
    assert body["refresh_token"] == "refresh-1"
    link_url, link_kwargs = calls[0]
    assert link_url == "https://test.supabase.co/auth/v1/admin/generate_link"
    assert link_kwargs["headers"]["Authorization"] == "Bearer service"
    assert link_kwargs["json"] == {"type": "magiclink", "email": "cesar@example.com"}
    verify_url, verify_kwargs = calls[1]
    assert verify_url == "https://test.supabase.co/auth/v1/verify"
    assert verify_kwargs["headers"] == {"apikey": "anon"}
    assert verify_kwargs["json"] == {"type": "magiclink", "token_hash": "hash-1"}


def test_companion_session_rejects_a_session_for_another_user(app_client):
    client, _ = app_client

    def post(url, **kwargs):
        if url.endswith("/admin/generate_link"):
            return _response(200, {"properties": {"hashed_token": "hash-1"}})
        return _response(200, {**SESSION, "user": {"id": "someone-else"}})

    with patch.object(companion_auth.httpx, "Client", return_value=_http_client(post)):
        res = client.post("/api/auth/companion-session", json={"client": "extension"})

    assert res.status_code == 403


def test_companion_session_requires_an_email(app_client):
    client, app = app_client
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": ""}
    res = client.post("/api/auth/companion-session", json={"client": "desktop"})
    assert res.status_code == 400


def test_companion_session_rejects_unknown_clients(app_client):
    client, _ = app_client
    res = client.post("/api/auth/companion-session", json={"client": "mobile"})
    assert res.status_code == 422


def test_companion_session_surfaces_upstream_failure(app_client):
    client, _ = app_client
    with patch.object(
        companion_auth.httpx,
        "Client",
        return_value=_http_client(lambda url, **kwargs: _response(500, {})),
    ):
        res = client.post("/api/auth/companion-session", json={"client": "desktop"})
    assert res.status_code == 502


def test_companion_refresh_returns_new_tokens(app_client):
    client, _ = app_client
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return _response(200, {**SESSION, "access_token": "access-2", "refresh_token": "refresh-2"})

    with patch.object(companion_auth.httpx, "Client", return_value=_http_client(post)):
        res = client.post("/api/auth/companion-refresh", json={"refresh_token": "refresh-1"})

    assert res.status_code == 200
    assert res.json()["access_token"] == "access-2"
    url, kwargs = calls[0]
    assert url == "https://test.supabase.co/auth/v1/token"
    assert kwargs["params"] == {"grant_type": "refresh_token"}
    assert kwargs["json"] == {"refresh_token": "refresh-1"}


def test_companion_refresh_maps_a_revoked_token_to_401(app_client):
    client, _ = app_client
    with patch.object(
        companion_auth.httpx,
        "Client",
        return_value=_http_client(lambda url, **kwargs: _response(400, {"error": "invalid_grant"})),
    ):
        res = client.post("/api/auth/companion-refresh", json={"refresh_token": "refresh-1"})
    assert res.status_code == 401
