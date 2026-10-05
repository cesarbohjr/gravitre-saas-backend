import pytest

from app.services.tool_types import ToolOutcomeUncertainError
from app.workflows.execution_engine_runtime import (
    _recovery_decision_for_failure,
    _recovery_kind,
    _status_from_rollup,
    _step_outcome_rollup,
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


def test_recovery_uses_catalog_identity_for_real_step_shape() -> None:
    # invoke_tool steps carry config.action (not tool_action); sends are writes by type.
    assert _recovery_kind("invoke_tool", {"action": "hubspot.contacts.update"}) == "write"
    assert _recovery_kind("invoke_tool", {"action": "hubspot.contacts.search"}) == "read"
    assert _recovery_kind("email_send", {}) == "write"
    assert _recovery_kind("agent", {}) == "agent_delegation"


def test_typed_uncertain_error_from_handler_requires_reconciliation() -> None:
    decision = _recovery_decision_for_failure(
        step_type="invoke_tool",
        config={"action": "hubspot.contacts.update"},
        error_code="step_failed",
        exc=ToolOutcomeUncertainError("no confirmation"),
        retries_used=1,
        retry_budget=3,
    )
    assert decision.requires_reconciliation is True
    assert decision.may_retry is False


def test_definite_read_failure_honours_retry_policy() -> None:
    decision = _recovery_decision_for_failure(
        step_type="invoke_tool",
        config={"action": "hubspot.contacts.search"},
        error_code="step_failed",
        exc=RuntimeError("hubspot.contacts.search failed: 500"),
        retries_used=1,
        retry_budget=3,
    )
    assert decision.may_retry is True


def _row(step_type: str, action: str = "", status: str = "completed", verification=None, **extra):
    output = {"invoke_action": action} if action else {}
    if verification is not None:
        output["verification"] = verification
    return {"step_type": step_type, "status": status, "output_snapshot": output, **extra}


_PROOF = {"verified": True, "method": "entity_get", "read_action": "hubspot.contacts.get"}


@pytest.mark.parametrize(
    ("rows", "run_status", "expected"),
    [
        ([_row("rag_retrieve"), _row("invoke_tool", "hubspot.contacts.search")], "completed", "completed"),
        ([_row("invoke_tool", "hubspot.contacts.update", verification=_PROOF)], "completed", "completed"),
        ([_row("invoke_tool", "hubspot.contacts.update")], "completed", "verification_inconclusive"),
        (
            [_row("email_send", "email.send", verification=_PROOF), _row("invoke_tool", "hubspot.contacts.update", status="failed")],
            "failed",
            "partial_success",
        ),
        (
            [_row("invoke_tool", "hubspot.contacts.update", status="failed", error_code="outcome_uncertain")],
            "failed",
            "verification_inconclusive",
        ),
        ([_row("invoke_tool", "hubspot.contacts.update", status="failed")], "failed", "failed"),
    ],
)
def test_run_status_is_bounded_by_per_step_proof(rows, run_status, expected) -> None:
    assert _status_from_rollup(run_status, _step_outcome_rollup(rows)) == expected


def test_one_proven_step_cannot_vouch_for_another() -> None:
    rows = [
        _row("invoke_tool", "hubspot.contacts.update", verification=_PROOF),
        _row("invoke_tool", "hubspot.deals.update"),
    ]
    outcome = _step_outcome_rollup(rows)
    assert (outcome.verified, outcome.unverified) == (1, 1)
    assert _status_from_rollup("completed", outcome) == "verification_inconclusive"


def test_graph_validation_error_is_importable_from_runtime() -> None:
    from app.workflows import execution_engine, execution_engine_runtime

    assert execution_engine_runtime.GraphValidationError is execution_engine.GraphValidationError
