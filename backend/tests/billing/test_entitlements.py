"""Tests for billing entitlement helpers."""
from __future__ import annotations

from app.billing.entitlements import compute_app_access, normalize_billing_status


def test_normalize_billing_status_defaults_to_trialing():
    assert normalize_billing_status(None) == "trialing"
    assert normalize_billing_status("  ACTIVE ") == "active"
    assert normalize_billing_status("canceled") == "cancelled"


def test_compute_app_access_trialing_and_active():
    assert compute_app_access("trialing")["can_access_app"] is True
    assert compute_app_access("active")["can_access_app"] is True
    assert compute_app_access("free")["can_access_app"] is True
    assert compute_app_access("inactive")["can_access_app"] is True


def test_compute_app_access_cancelled_blocks():
    result = compute_app_access("cancelled")
    assert result["can_access_app"] is False
    assert result["requires_upgrade"] is True
    assert result["upgrade_reason"] == "subscription_cancelled"


def test_compute_app_access_past_due_blocks_access():
    result = compute_app_access("past_due")
    assert result["can_access_app"] is False
    assert result["requires_upgrade"] is True
    assert result["upgrade_reason"] == "payment_past_due"


def test_compute_app_access_expired_trial_blocks():
    past = "2020-01-01T00:00:00+00:00"
    result = compute_app_access("trialing", trial_ends_at=past)
    assert result["can_access_app"] is False
    assert result["upgrade_reason"] == "trial_expired"
