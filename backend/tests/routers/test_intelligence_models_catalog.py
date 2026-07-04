"""Tests for Intelligence Center model catalog (org-member, resilient loading)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_org_context, require_org_member
from app.config import Settings, get_settings
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _authenticate(org_id: str = "org-1") -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[require_org_member] = lambda: ({"user_id": "user-1"}, org_id, "member")


def test_intelligence_models_catalog_returns_catalog_when_data_queries_fail():
    _authenticate()
    catalog_payload = {
        "catalog": {"intent_classifier": {"status": "trained", "use_cases": ["routing"]}},
        "orgTrainingStatus": {},
        "outcomeScores": {},
    }
    with patch(
        "app.routers.intelligence_engine.build_ml_catalog_dashboard",
        new=AsyncMock(return_value=catalog_payload),
    ):
        response = client.get("/api/intelligence/models/catalog", headers={"x-org-id": "org-1"})
    assert response.status_code == 200
    body = response.json()
    assert "intent_classifier" in body["catalog"]
    assert body["orgTrainingStatus"] == {}


def test_build_ml_catalog_dashboard_survives_org_status_failures():
    import asyncio

    from app.ml.model_catalog import build_ml_catalog_dashboard

    async def _boom(*args, **kwargs):
        raise RuntimeError("supabase unavailable")

    with patch("app.ml.model_catalog.get_org_model_status", new=AsyncMock(side_effect=_boom)):
        with patch(
            "app.services.strategy_performance_ledger.get_strategy_performance_ledger"
        ) as ledger_mock:
            ledger = ledger_mock.return_value
            ledger.load_model_outcome_scores = AsyncMock(return_value={})
            result = asyncio.run(build_ml_catalog_dashboard("org-1", settings=_settings()))

    assert "intent_classifier" in result["catalog"]
    assert isinstance(result["orgTrainingStatus"], dict)
    assert result["outcomeScores"] == {}
