"""Phase 2 connector deployed smoke endpoint."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.support.build_insights import authenticate, clear_overrides, client, make_test_settings


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


@patch("app.routers.ops_internal.get_supabase_client")
def test_phase2_connector_smoke_wiring(mock_client):
    mock_client.return_value = MagicMock()
    settings = make_test_settings()
    settings.internal_api_secret = "test-secret"
    from app.config import get_settings

    authenticate()
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: settings

    with patch(
        "app.operators.react_engine.ReActEngine._execute_tool_call",
        new=AsyncMock(return_value={"success": True, "action": "linear.issues.list"}),
    ):
        with patch(
            "app.services.tool_registry.ToolRegistry.list_connected_integrations",
            return_value=["linear"],
        ):
            response = client.post(
                "/api/internal/ops/phase2-connector-smoke",
                headers={"X-Internal-Secret": "test-secret"},
                json={
                    "org_id": "org-1",
                    "actor_id": "user-1",
                    "environment_name": "production",
                    "invoke_reads": True,
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["wiring"]["pass"] is True
    assert body["wiring"]["route_count"] == 30
    assert body["oauth_registry"]["pass"] is True
    assert body["vendors"]["linear"]["pass"] is True


def test_phase2_connector_smoke_requires_secret():
    authenticate()
    response = client.post(
        "/api/internal/ops/phase2-connector-smoke",
        json={"org_id": "org-1", "actor_id": "user-1"},
    )
    assert response.status_code in {401, 503}
