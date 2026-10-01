from app.capabilities.repository import rollback_status_for_snapshot


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
