"""Tests for /api/meson routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.main import app
from app.services.meson_service import (
    MesonDeployResult,
    MesonGeneratedConfig,
    MesonInterpretResult,
    MesonService,
    MesonSuggestion,
    MesonSuggestionsResponse,
    get_meson_service,
)

client = TestClient(app)


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
    from app.middleware.entitlements import TIER_FEATURES, TIER_LIMITS, get_entitlements_dependency

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "default"
    app.dependency_overrides[get_entitlements_dependency] = lambda: {
        "tier": "control",
        "status": "active",
        "seat_count": 1,
        "lite_seats": 0,
        "limits": dict(TIER_LIMITS["control"]),
        "features": dict(TIER_FEATURES["control"]),
        "addons": [],
        "usage": {},
    }


def _mock_meson_service() -> MesonService:
    mock = MagicMock(spec=MesonService)
    plan = MesonInterpretResult(
        intent="Build sales follow-up automation",
        department="sales",
        systems=["crm"],
        outputTypes=["workflows"],
        generatedConfig=MesonGeneratedConfig(
            agent="Sales Agent",
            agent_role="Sales specialist",
            agent_description="Automates follow-ups",
            training=["CRM playbooks"],
            workflows=["Follow-up workflow"],
            sample_outputs=["Weekly pipeline summary"],
        ),
        confidence=0.8,
        explanation="Mock plan",
    )
    mock.interpret_build_request = AsyncMock(return_value=plan)
    mock.deploy_build = AsyncMock(
        return_value=MesonDeployResult(agentId="agent-123", workflowId="wf-456", result=plan)
    )
    mock.get_workflow_suggestions = MagicMock(
        return_value=MesonSuggestionsResponse(
            suggestions=[
                MesonSuggestion(
                    id="add-approval",
                    nodeType="approval",
                    label="Quality Gate",
                    reason="Add approval step before production?",
                    confidence=0.82,
                )
            ]
        )
    )
    mock.load_dismissed_suggestion_ids = MagicMock(return_value=set())
    mock.load_feedback_summary = MagicMock(
        return_value={
            "dismissed_ids": set(),
            "by_suggestion": {},
            "accepted_count": 0,
            "dismissed_count": 0,
        }
    )
    mock.get_feedback_metrics = MagicMock(
        return_value={
            "acceptedCount": 3,
            "dismissedCount": 1,
            "acceptanceRate": 0.75,
            "suggestions": [],
        }
    )
    mock.detect_anomalies = MagicMock(return_value={"alerts": []})
    mock.get_proactive_insights = MagicMock(return_value={"insights": []})
    mock.get_page_context = MagicMock(return_value={"insights": [], "suggestions": [], "source": "ai-chat"})
    mock.get_workflow_optimizations = MagicMock(return_value={"insights": []})
    mock.record_feedback = MagicMock(return_value={"ok": True})
    mock.get_user_preferences = MagicMock(
        return_value={
            "department": "sales",
            "systems": ["crm"],
            "outputTypes": ["workflows"],
            "preferredBuildHoursUtc": [14],
            "interpretCount": 2,
            "deployCount": 1,
        }
    )
    return mock


def test_interpret_requires_org():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    response = client.post(
        "/api/meson/interpret",
        json={"intent": "Build a support triage agent", "department": "operations", "systems": [], "outputTypes": []},
    )
    assert response.status_code == 403


def test_interpret_returns_plan():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    response = client.post(
        "/api/meson/interpret",
        json={
            "intent": "Build a support triage agent",
            "department": "operations",
            "systems": ["messaging"],
            "outputTypes": ["workflows"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["generatedConfig"]["agent"] == "Sales Agent"
    assert body["systems"] == ["crm"]
    mock.interpret_build_request.assert_awaited_once()


def test_deploy_creates_resources():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, "org-1")
    response = client.post(
        "/api/meson/deploy",
        json={
            "intent": "Build a support triage agent",
            "department": "operations",
            "systems": ["messaging"],
            "outputTypes": ["workflows"],
            "generatedConfig": {"agent": "Ops Agent"},
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["agentId"] == "agent-123"
    assert body["workflowId"] == "wf-456"
    mock.deploy_build.assert_awaited_once()


def test_suggestions_returns_builder_hints():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    response = client.post(
        "/api/meson/suggestions",
        json={
            "workflowState": {"nodes": [{"type": "source", "name": "Ingest"}]},
            "lastAddedNode": {"type": "source"},
            "workflowId": "wf-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"][0]["id"] == "add-approval"
    mock.load_feedback_summary.assert_called_once()
    mock.get_workflow_suggestions.assert_called_once()


def test_alerts_and_insights_return_lists():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    alerts = client.get("/api/meson/alerts")
    insights = client.get("/api/meson/insights")
    assert alerts.status_code == 200
    assert insights.status_code == 200
    assert alerts.json()["alerts"] == []
    assert insights.json()["insights"] == []
    mock.detect_anomalies.assert_called_once()
    mock.get_proactive_insights.assert_called_once()


def test_workflow_optimizations_returns_insights():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    response = client.get("/api/meson/optimizations/wf-1")
    assert response.status_code == 200
    assert response.json()["insights"] == []
    mock.get_workflow_optimizations.assert_called_once()


def test_page_context_returns_insights_and_suggestions():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    response = client.get("/api/meson/page-context?page=model-registry")
    assert response.status_code == 200
    body = response.json()
    assert body["insights"] == []
    assert body["suggestions"] == []
    mock.get_page_context.assert_called_once()


def test_feedback_metrics_returns_acceptance_rate():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    response = client.get("/api/meson/feedback/metrics?workflow_id=wf-1")
    assert response.status_code == 200
    body = response.json()
    assert body["acceptanceRate"] == 0.75
    mock.get_feedback_metrics.assert_called_once()


def test_preferences_returns_learned_profile():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    response = client.get("/api/meson/preferences")
    assert response.status_code == 200
    body = response.json()
    assert body["department"] == "sales"
    assert body["interpretCount"] == 2
    mock.get_user_preferences.assert_called_once()


def test_feedback_records_action():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    response = client.post(
        "/api/meson/feedback",
        json={
            "suggestionId": "add-approval",
            "action": "dismissed",
            "workflowId": "wf-1",
        },
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    mock.record_feedback.assert_called_once()
