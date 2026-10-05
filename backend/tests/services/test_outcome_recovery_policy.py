from app.services.outcome_recovery_policy import decide_recovery


def test_uncertain_write_reconciles_before_retry() -> None:
    d = decide_recovery(kind="write", error_code="timeout", outcome_uncertain=True)
    assert d.action == "reconcile"
    assert d.requires_reconciliation is True
    assert d.may_retry is False


def test_read_timeout_has_bounded_retry() -> None:
    d = decide_recovery(kind="read", error_code="timeout", retries_used=0, retry_budget=1)
    assert d.action == "retry"
    assert d.may_retry is True


def test_exhausted_retry_can_replan_to_alternate() -> None:
    d = decide_recovery(
        kind="read",
        error_code="timeout",
        retries_used=1,
        retry_budget=1,
        alternate_capability_available=True,
    )
    assert d.action == "replan"


def test_auth_problem_is_user_or_connection_blocked_not_retry_loop() -> None:
    d = decide_recovery(kind="write", error_code="auth_expired")
    assert d.action == "blocked"
    assert d.may_retry is False
