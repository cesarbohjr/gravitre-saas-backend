"""Tests for knowledge sync internal/admin routes (STA-45)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import Settings, get_settings
from app.main import app


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(autouse=True)
def _clear_settings_override():
    app.dependency_overrides.pop(get_settings, None)
    yield
    app.dependency_overrides.pop(get_settings, None)


async def test_internal_sync_due_requires_secret_configured(async_client):
    resp = await async_client.post("/api/internal/knowledge/sync-due")
    assert resp.status_code == 503


async def test_internal_sync_due_rejects_bad_secret(async_client):
    app.dependency_overrides[get_settings] = lambda: _settings(internal_api_secret="right-secret")
    resp = await async_client.post(
        "/api/internal/knowledge/sync-due",
        headers={"X-Internal-Secret": "wrong-secret"},
    )
    assert resp.status_code == 401


async def test_internal_sync_due_accepts_valid_secret(async_client, monkeypatch):
    app.dependency_overrides[get_settings] = lambda: _settings(internal_api_secret="right-secret")

    import app.routers.knowledge_sync as knowledge_sync_router

    monkeypatch.setattr(
        knowledge_sync_router,
        "run_scheduled_knowledge_syncs",
        lambda settings: {"due_count": 0, "processed": 0, "outcomes": []},
    )

    resp = await async_client.post(
        "/api/internal/knowledge/sync-due",
        headers={"X-Internal-Secret": "right-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["processed"] == 0
