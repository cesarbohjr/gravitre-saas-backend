"""Tests for standardized plan-limit 402 error shapes."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.billing.entitlement_service import PlanLimitExceededError
from app.billing.service import require_limit


def _shape(err: HTTPException) -> dict:
    assert isinstance(err.detail, dict)
    return err.detail


def test_agent_limit_exceeded_returns_standard_shape():
    err = PlanLimitExceededError("agent_count", current=2, max_allowed=2)
    detail = _shape(err)
    assert detail["error"] == "plan_limit_exceeded"
    assert detail["limit_type"] == "agent_count"
    assert detail["current"] == 2
    assert detail["max"] == 2
    assert detail["upgrade_url"] == "/settings/billing"
    assert err.status_code == 402


def test_workflow_limit_exceeded_returns_standard_shape():
    with pytest.raises(PlanLimitExceededError) as exc:
        require_limit(10, 10, "workflows")
    detail = exc.value.detail
    assert detail["limit_type"] == "workflow_count"
    assert detail["error"] == "plan_limit_exceeded"


def test_connector_limit_exceeded_returns_standard_shape():
    err = PlanLimitExceededError("connector_count", current=5, max_allowed=5)
    detail = _shape(err)
    assert detail["limit_type"] == "connector_count"


def test_marketplace_install_limit_exceeded_returns_standard_shape():
    from app.marketplace.service import _check_plan_limits

    class FakeResult:
        data = [{"id": "wf-1"}] * 10

    class FakeClient:
        def table(self, name: str):
            assert name == "workflow_defs"
            return self

        def select(self, *_cols):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def execute(self):
            return FakeResult()

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(
            "app.marketplace.service.get_plan_for_org",
            lambda client, org_id: {"workflows_limit": 10},
        )
        monkeypatch.setattr(
            "app.marketplace.service.list_operators",
            lambda client, org_id: [],
        )
        with pytest.raises(PlanLimitExceededError) as exc:
            _check_plan_limits(FakeClient(), "org-1", "workflow")
        detail = exc.value.detail
        assert detail["error"] == "plan_limit_exceeded"
        assert detail["limit_type"] == "workflow_count"
    finally:
        monkeypatch.undo()


def test_environment_limit_exceeded_returns_standard_shape():
    with pytest.raises(PlanLimitExceededError) as exc:
        require_limit(1, 1, "environments")
    assert exc.value.detail["limit_type"] == "environment_count"


def test_all_limit_types_produce_identical_response_structure():
    samples = [
        PlanLimitExceededError("agent_count", 1, 1),
        PlanLimitExceededError("workflow_count", 1, 1),
        PlanLimitExceededError("connector_count", 1, 1),
        PlanLimitExceededError("marketplace_install", 1, 1),
    ]
    keys = {"error", "limit_type", "current", "max", "upgrade_url"}
    for err in samples:
        detail = _shape(err)
        assert set(detail.keys()) == keys
        assert detail["error"] == "plan_limit_exceeded"
        assert detail["upgrade_url"] == "/settings/billing"
