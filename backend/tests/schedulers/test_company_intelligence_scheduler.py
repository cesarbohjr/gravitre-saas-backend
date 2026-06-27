from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.schedulers import company_intelligence_scheduler as scheduler_module


@pytest.mark.asyncio
async def test_scheduler_respects_interval_env_var(monkeypatch):
    monkeypatch.setattr(
        "app.schedulers.company_intelligence_scheduler.get_settings",
        lambda: Settings(company_intelligence_interval_seconds=21600),
    )
    created: dict[str, int] = {}

    def fake_create_task(coro):
        created["interval"] = 21600
        coro.close()
        return AsyncMock()

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)
    task = scheduler_module.start_company_intelligence_scheduler()
    assert task is not None
    assert created["interval"] == 21600


def test_scheduler_disabled_when_interval_zero(monkeypatch):
    monkeypatch.setattr(
        "app.schedulers.company_intelligence_scheduler.get_settings",
        lambda: Settings(company_intelligence_interval_seconds=0),
    )
    assert scheduler_module.start_company_intelligence_scheduler() is None


@pytest.mark.asyncio
async def test_active_org_selection_respects_7_day_window(monkeypatch):
    captured: dict[str, int] = {}

    def fake_get_active_org_ids(settings, *, since_days=7, limit=20, client=None):
        captured["since_days"] = since_days
        return ["org-1"]

    monkeypatch.setattr(scheduler_module, "get_active_org_ids", fake_get_active_org_ids)
    monkeypatch.setattr(scheduler_module, "run_company_intelligence_for_org_sync", lambda *_a, **_k: {"ok": True})
    await scheduler_module._run_once(Settings())
    assert captured["since_days"] == 7


@pytest.mark.asyncio
async def test_active_org_selection_caps_at_limit(monkeypatch):
    monkeypatch.setattr(
        scheduler_module,
        "get_active_org_ids",
        lambda *_a, **_k: [f"org-{i}" for i in range(20)],
    )
    calls: list[str] = []

    def fake_run(org_id, settings=None):
        calls.append(org_id)
        return {"org_id": org_id}

    monkeypatch.setattr(scheduler_module, "run_company_intelligence_for_org_sync", fake_run)
    await scheduler_module._run_once(Settings())
    assert len(calls) == 20


@pytest.mark.asyncio
async def test_manual_trigger_endpoint_requires_internal_secret():
    from fastapi import HTTPException

    from app.routers.ops_internal import require_internal_secret

    settings = Settings(internal_api_secret="secret")
    with pytest.raises(HTTPException) as exc:
        await require_internal_secret(settings, x_internal_secret="wrong")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_manual_trigger_can_target_single_org():
    from app.routers.ops_internal import CompanyIntelligenceRunRequest, company_intelligence_run_cron

    settings = Settings(internal_api_secret="secret")
    with patch(
        "app.services.company_intelligence_orchestrator.CompanyIntelligenceOrchestrator.run_for_org",
        new=AsyncMock(return_value={"org_id": "org-1", "workflow_rows": 40}),
    ):
        result = await company_intelligence_run_cron(
            CompanyIntelligenceRunRequest(org_id="org-1"),
            settings=settings,
            _=None,
        )
    assert result["processed"] == 1
    assert result["results"][0]["org_id"] == "org-1"
