"""Tests for feedback mode admin routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_org_context, require_admin
from app.routers import feedback_mode


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(feedback_mode.router)
    app.dependency_overrides[get_org_context] = lambda: "org-1"
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, "org-1")
    return TestClient(app)


def test_get_feedback_mode_settings():
    client = _build_client()
    with patch(
        "app.routers.feedback_mode.get_mode_b_feedback_service",
    ) as mock_factory:
        mock_factory.return_value.get_feedback_settings = AsyncMock(
            return_value={"feedbackMode": "mode_a", "orgId": "org-1"}
        )
        response = client.get("/api/admin/feedback-mode")
    assert response.status_code == 200
    assert response.json()["feedbackMode"] == "mode_a"
