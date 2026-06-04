"""Tests for workflow schedule internal cron route (STA-47)."""
from __future__ import annotations

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


async def test_internal_dispatch_requires_secret_configured(async_client):
    resp = await async_client.post("/api/internal/workflows/schedules/dispatch-due")
    assert resp.status_code == 503


async def test_internal_dispatch_accepts_valid_secret(async_client, monkeypatch):
    app.dependency_overrides[get_settings] = lambda: _settings(internal_api_secret="right-secret")

    import app.routers.workflow_schedules_internal as schedules_router

    async def _fake_dispatch(settings):
        return {"due_count": 0, "processed": 0, "outcomes": []}

    monkeypatch.setattr(schedules_router, "dispatch_due_workflow_schedules", lambda settings: {"due_count": 0, "processed": 0, "outcomes": []})

    resp = await async_client.post(
        "/api/internal/workflows/schedules/dispatch-due",
        headers={"X-Internal-Secret": "right-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["processed"] == 0
