from app.workflows.execution_engine_runtime import (
    _recovery_decision_for_failure,
    _recovery_kind,
)


def test_mutating_action_is_classified_as_write() -> None:
    assert _recovery_kind("connector", {"tool_action": "hubspot.contacts.create"}) == "write"


def test_uncertain_mutation_timeout_requires_reconciliation_not_retry() -> None:
    decision = _recovery_decision_for_failure(
        step_type="connector",
        config={"tool_action": "hubspot.contacts.create"},
        error_code="timeout",
        exc=TimeoutError("socket closed after request"),
        retries_used=1,
        retry_budget=3,
    )
    assert decision.action == "reconcile"
    assert decision.may_retry is False
    assert decision.requires_reconciliation is True


def test_read_timeout_can_use_bounded_retry() -> None:
    decision = _recovery_decision_for_failure(
        step_type="connector",
        config={"tool_action": "hubspot.contacts.search"},
        error_code="timeout",
        exc=TimeoutError("timeout"),
        retries_used=1,
        retry_budget=3,
    )
    assert decision.action == "retry"
    assert decision.may_retry is True
