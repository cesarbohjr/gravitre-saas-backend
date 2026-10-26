"""GET /api/goals/templates returns each template with its cadence."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.main import app
from app.services.goal_templates import GOAL_FREQUENCIES


def test_goal_templates_carry_a_valid_cadence():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
    try:
        response = TestClient(app).get("/api/goals/templates")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    templates = response.json()["templates"]
    assert {t["id"] for t in templates} == {"marketing-signups", "finance-overdue", "support-response"}
    assert all(t["frequency"] in GOAL_FREQUENCIES for t in templates)
