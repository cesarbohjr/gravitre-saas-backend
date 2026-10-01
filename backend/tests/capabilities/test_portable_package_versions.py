from app.capabilities.repository import (
    _clear_time_sensitive_publisher_trust,
    rollback_status_for_snapshot,
)


def test_safe_snapshot_can_restore_installed() -> None:
    assert rollback_status_for_snapshot(
        {"license_policy": "allow", "risk_level": "low"}
    ) == "installed"


def test_high_risk_snapshot_requires_review_after_restore() -> None:
    assert rollback_status_for_snapshot(
        {"license_policy": "allow", "risk_level": "high"}
    ) == "quarantined"


def test_blocked_license_requires_review_after_restore() -> None:
    assert rollback_status_for_snapshot(
        {"license_policy": "block", "risk_level": "low"}
    ) == "quarantined"


def test_rollback_never_restores_historical_publisher_trust() -> None:
    patch = {
        "publisher_trusted": True,
        "publisher_trust_scope": "marketplace_verified",
        "publisher_verified": True,
        "marketplace_publisher_id": "publisher-1",
    }
    reset = _clear_time_sensitive_publisher_trust(patch)
    assert reset["publisher_trusted"] is False
    assert reset["publisher_trust_scope"] == "none"
    assert reset["publisher_verified"] is False
    assert reset["marketplace_publisher_id"] is None
