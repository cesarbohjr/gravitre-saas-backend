"""Tests for billing entitlement service (trial expiry P0)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.billing.entitlement_service import (
    PlanRequiredError,
    assert_org_not_blocked,
    get_org_billing_state,
    resolve_billing_state,
    should_gate_path,
)
from app.billing.entitlements import compute_app_access


def test_trial_expiry_computed_from_trial_ends_at_not_stripe_status_alone():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    state = resolve_billing_state(
        billing_row={"billing_status": "trialing", "plan_code": "node"},
        trial_ends_at=past,
    )
    assert state["status"] == "trial_expired"
    assert state["is_blocked"] is True


def test_trial_active_allows_access():
    future = datetime.now(timezone.utc) + timedelta(days=3)
    state = resolve_billing_state(
        billing_row={"billing_status": "trialing", "plan_code": "node"},
        trial_ends_at=future,
    )
    assert state["status"] == "trialing"
    assert state["is_blocked"] is False
    assert state["days_remaining_in_trial"] in {2, 3}


def test_compute_app_access_blocks_expired_trial():
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    access = compute_app_access("trialing", trial_ends_at=past)
    assert access["can_access_app"] is False
    assert access["requires_upgrade"] is True
    assert access["upgrade_reason"] == "trial_expired"


def test_compute_app_access_past_due_blocks():
    access = compute_app_access("past_due")
    assert access["can_access_app"] is False
    assert access["upgrade_reason"] == "payment_past_due"


def test_plan_required_error_shape():
    err = PlanRequiredError("trial_expired")
    assert err.status_code == 402
    assert err.detail["error"] == "plan_required"
    assert err.detail["subscription_status"] == "trial_expired"
    assert err.detail["upgrade_url"] == "/settings/billing"


def test_plan_limit_exceeded_error_shape():
    from app.billing.entitlement_service import PlanLimitExceededError

    err = PlanLimitExceededError("agent_count", current=2, max_allowed=2)
    assert err.status_code == 402
    assert err.detail == {
        "error": "plan_limit_exceeded",
        "limit_type": "agent_count",
        "current": 2,
        "max": 2,
        "upgrade_url": "/settings/billing",
    }


def test_should_gate_path_allowlist():
    assert should_gate_path("/api/billing/status") is False
    assert should_gate_path("/api/auth/me") is False
    assert should_gate_path("/api/agent-jobs") is True
    assert should_gate_path("/api/workflows/execute") is True


def test_assert_org_not_blocked_raises(monkeypatch):
    class FakeClient:
        pass

    monkeypatch.setattr(
        "app.billing.entitlement_service.get_org_billing",
        lambda client, org_id: {"billing_status": "trialing", "plan_code": "node", "current_period_end": None},
    )
    monkeypatch.setattr(
        "app.billing.entitlement_service._load_trial_ends_at",
        lambda client, org_id, billing: datetime.now(timezone.utc) - timedelta(days=1),
    )
    monkeypatch.setattr("app.billing.entitlement_service._is_sandbox_exempt", lambda client, org_id: False)

    with pytest.raises(PlanRequiredError) as exc:
        assert_org_not_blocked(FakeClient(), "org-1")
    assert exc.value.detail["error"] == "plan_required"


def test_get_org_billing_state_integration_shape(monkeypatch):
    past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    class FakeClient:
        pass

    monkeypatch.setattr(
        "app.billing.entitlement_service.get_org_billing",
        lambda client, org_id: {
            "plan_code": "node",
            "billing_status": "trialing",
            "current_period_end": past_iso,
        },
    )
    monkeypatch.setattr(
        "app.billing.entitlement_service._load_trial_ends_at",
        lambda client, org_id, billing: datetime.fromisoformat(past_iso.replace("Z", "+00:00")),
    )
    monkeypatch.setattr("app.billing.entitlement_service._is_sandbox_exempt", lambda client, org_id: False)

    state = get_org_billing_state(FakeClient(), "org-1")
    assert state["status"] == "trial_expired"
    assert state["is_blocked"] is True
