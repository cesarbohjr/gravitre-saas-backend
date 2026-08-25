"""Ops smoke endpoints for capability phases 3-4 and pre-action card."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.support.build_insights import authenticate, clear_overrides, client, make_test_settings


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


def _auth_with_internal_secret():
    settings = make_test_settings()
    settings.internal_api_secret = "test-secret"
    from app.config import get_settings
    from app.main import app

    authenticate()
    app.dependency_overrides[get_settings] = lambda: settings


@patch("app.routers.ops_internal.get_supabase_client")
def test_capability_recipes_smoke(mock_client):
    mock_client.return_value = MagicMock()
    _auth_with_internal_secret()
    with patch(
        "app.services.tool_registry.ToolRegistry.list_connected_integrations",
        return_value=["hubspot", "slack", "google_drive"],
    ):
        response = client.post(
            "/api/internal/ops/capability-recipes-smoke",
            headers={"X-Internal-Secret": "test-secret"},
            json={"org_id": "org-1", "actor_id": "user-1"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["recipe_count"] >= 3
    assert body["resolved"]["recipeId"] == "sales.new-lead-enrichment"


@patch("app.routers.ops_internal.get_supabase_client")
def test_capability_conversational_grace_smoke(mock_client):
    mock_client.return_value = MagicMock()
    _auth_with_internal_secret()
    blocked = {
        "success": False,
        "tool": "capability__crm__contact__create",
        "action": "hubspot.contacts.create",
        "integration": "hubspot",
        "label": "HubSpot contact",
        "pending_approval": True,
        "error_code": "write_approval_required",
        "user_message": "I'll create that after you confirm in your HubSpot (HubSpot contact).",
        "args": {},
    }
    with patch(
        "app.operators.react_engine.ReActEngine._execute_tool_call",
        new=AsyncMock(return_value=blocked),
    ):
        response = client.post(
            "/api/internal/ops/capability-conversational-grace-smoke",
            headers={"X-Internal-Secret": "test-secret"},
            json={"org_id": "org-1", "actor_id": "user-1"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["pass"] is True
    assert body["checks"]["approval_message_graceful"] is True


@patch("app.routers.ops_internal.get_supabase_client")
def test_pre_action_card_smoke(mock_client):
    mock_client.return_value = MagicMock()
    _auth_with_internal_secret()
    blocked = {
        "success": False,
        "tool": "capability__crm__contact__create",
        "action": "hubspot.contacts.create",
        "integration": "hubspot",
        "label": "HubSpot contact",
        "pending_approval": True,
        "error_code": "write_approval_required",
        "args": {"email": "x@example.com"},
    }
    with patch(
        "app.operators.react_engine.ReActEngine._execute_tool_call",
        new=AsyncMock(return_value=blocked),
    ):
        with patch(
            "app.services.chat_connector_execution_service.ChatConnectorExecutionService._evaluate_risk",
            new=AsyncMock(
                return_value={
                    "estimated_impact": "medium",
                    "risk_level": "low",
                    "approval_reason": "write_requires_approval",
                }
            ),
        ):
            response = client.post(
                "/api/internal/ops/pre-action-card-smoke",
                headers={"X-Internal-Secret": "test-secret"},
                json={"org_id": "org-1", "actor_id": "user-1"},
            )
    assert response.status_code == 200
    body = response.json()
    assert body["pass"] is True
    assert body["pending_params"]["risk_level"] == "low"
