"""Tests for ops internal cron endpoints."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.support.build_insights import authenticate, clear_overrides, client, make_test_settings


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


@patch("app.routers.ops_internal.get_supabase_client")
def test_rollup_daily_requires_internal_secret(mock_client):
    authenticate()
    response = client.post("/api/internal/ops/rollup-daily", json={"days": 1})
    assert response.status_code in {401, 503}


@patch("app.routers.ops_internal.run_connector_health_monitor")
def test_connector_health_cron(mock_health):
    mock_health.return_value = {"checked": 2, "updated": 1, "errors": 0}
    settings = make_test_settings()
    settings.internal_api_secret = "test-secret"
    from app.config import get_settings

    authenticate()
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: settings
    response = client.post(
        "/api/internal/ops/connector-health",
        headers={"X-Internal-Secret": "test-secret"},
    )
    assert response.status_code == 200
    assert response.json()["checked"] == 2
