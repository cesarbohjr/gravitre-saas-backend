from app.capabilities.review import review_transition_allowed


def test_high_risk_package_requires_admin_review_but_can_be_activated() -> None:
    assert review_transition_allowed(
        current_status="quarantined",
        target_status="installed",
        risk_level="high",
        license_policy="allow",
    )


def test_blocked_license_cannot_be_activated() -> None:
    assert not review_transition_allowed(
        current_status="quarantined",
        target_status="installed",
        risk_level="blocked",
        license_policy="block",
    )
