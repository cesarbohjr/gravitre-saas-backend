"""Outcome Ownership: a confirmed retry of an uncertain chat write reconciles first."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.chat_connector_execution_service import ChatConnectorExecutionService
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.outcome_reconciliation import ReconciliationResult


class _State:
    def __init__(self, pending: dict[str, Any]) -> None:
        self.state: dict[str, Any] = {"pending_task": dict(pending)}

    async def get_task_state(self, *_a, **_k) -> dict[str, Any]:
        return dict(self.state)

    async def update_task_state(self, _cid, _org, patch_: dict[str, Any], **_k) -> None:
        self.state.update(patch_)


def _service(state: _State) -> ChatConnectorExecutionService:
    svc = ChatConnectorExecutionService.__new__(ChatConnectorExecutionService)
    svc.settings = MagicMock()
    svc._state = state
    return svc


_PLAN = ConnectorActionPlan(
    tool_name="hubspot_contacts_create",
    invoke_action="hubspot.contacts.create",
    integration="hubspot",
    kind="write",
    label="Create contact Ada",
    args={"email": "ada@example.com"},
)


def _gate(state: _State, recon: ReconciliationResult):
    svc = _service(state)
    with patch(
        "app.services.outcome_reconciliation.reconcile_uncertain_write", return_value=recon
    ) as reconcile:
        result = asyncio.run(
            svc._claim_write_before_invoke(
                "conv",
                "org",
                state.state,
                client=MagicMock(),
                plan=_PLAN,
                actor_id="user",
                ctx=MagicMock(),
            )
        )
    return result, reconcile


def test_applied_write_is_reported_done_and_never_rerun() -> None:
    state = _State({"type": "connector_action", "status": "outcome_uncertain"})
    result, reconcile = _gate(
        state,
        ReconciliationResult(
            "applied",
            "found_by_email",
            "42",
            "hubspot.contacts.search",
            {"verified": True, "method": "reconcile_lookup", "read_action": "hubspot.contacts.search"},
        ),
    )
    reconcile.assert_called_once()
    assert result is not None and result.success is True
    assert result.outcome_verified is True
    assert "did not run it again" in result.body
    assert state.state["pending_task"]["status"] == "executed"


def test_proven_absent_write_runs_once() -> None:
    state = _State({"type": "connector_action", "status": "outcome_uncertain"})
    result, _ = _gate(state, ReconciliationResult("not_applied", "no_record_with_email"))
    # None = the claim succeeded and the caller proceeds to invoke exactly once.
    assert result is None
    assert state.state["pending_task"]["status"] == "executing"


def test_unknown_state_stays_blocked_with_honest_copy() -> None:
    state = _State({"type": "connector_action", "status": "awaiting_reconciliation"})
    result, _ = _gate(state, ReconciliationResult("unknown", "lookup_inconclusive"))
    assert result is not None and result.success is False
    assert result.error_code == "OUTCOME_UNCERTAIN"
    assert "won't run it again" in result.body


@pytest.mark.parametrize("error_code", ["OUTCOME_UNCERTAIN"])
def test_uncertain_result_finalizes_inconclusive_not_failed(error_code: str) -> None:
    from app.services.conversational_execution_service import ExecutionResult

    svc = _service(_State({}))
    result = ExecutionResult(
        success=False,
        entity_type="connector",
        entity_id="",
        title="Create contact Ada",
        body="not confirmed",
        error_code=error_code,
    )
    with (
        patch("app.workflows.repository.create_run", return_value={"id": "run-1"}),
        patch("app.workflows.repository.create_step", return_value={"id": "s1"}),
        patch("app.workflows.repository.update_step"),
        patch("app.services.execution_outcome.finalize_execution_outcome") as finalize,
    ):
        svc._finalize_connector_outcome(
            MagicMock(), org_id="org", user_id="user", conversation_id="conv", plan=_PLAN, result=result
        )
    assert finalize.call_args.kwargs["status"] == "verification_inconclusive"
