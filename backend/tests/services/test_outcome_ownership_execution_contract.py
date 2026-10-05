"""Outcome Ownership: conversational execute (agents, workflows, runs) behaves truthfully.

Behavioral replacements for the earlier source-text assertions.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import conversational_execution_service as ces
from app.services.conversational_execution_service import ConversationalExecutionService, ExecutionResult


class _State:
    def __init__(self, pending: dict[str, Any] | None = None) -> None:
        self.state: dict[str, Any] = {"pending_task": dict(pending or {})}

    async def get_task_state(self, *_a, **_k) -> dict[str, Any]:
        return dict(self.state)

    async def update_task_state(self, _cid, _org, patch_: dict[str, Any], **_k) -> None:
        self.state.update(patch_)


def _service(state: _State) -> ConversationalExecutionService:
    svc = ConversationalExecutionService.__new__(ConversationalExecutionService)
    svc.settings = MagicMock()
    svc._state = state
    return svc


def _run(svc: ConversationalExecutionService, task_type: str = "create_agent") -> ExecutionResult:
    return asyncio.run(
        svc.execute_task(
            org_id="org",
            user_id="user",
            conversation_id="conv",
            task_type=task_type,
            clarified={"agent_name": "Scout", "agent_purpose": "research"},
            client=MagicMock(),
            classification={},
        )
    )


def _agent(verified: bool) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        entity_type="agent",
        entity_id="a1",
        title="Scout",
        body="Created agent “Scout”.",
        structured={
            "verification": {
                "verified": verified,
                "method": "gravitre_read_back",
                "read_action": "operators.get",
            }
        },
        outcome_verified=verified,
    )


def test_execute_task_finalizes_with_terminal_status_and_does_not_crash() -> None:
    svc = _service(_State({"type": "create_agent", "status": "awaiting_confirm"}))
    with (
        patch.object(svc, "_create_agent", new=AsyncMock(return_value=_agent(True))),
        patch("app.services.execution_outcome.finalize_execution_outcome") as finalize,
        patch.object(svc, "_record_learning_outcome", new=AsyncMock()),
    ):
        result = _run(svc)
    assert result.success and result.outcome_verified
    assert finalize.call_args.kwargs["status"] == "completed"
    assert finalize.call_args.kwargs["metadata"]["verification"]["method"] == "gravitre_read_back"


def test_unconfirmed_read_back_is_inconclusive_not_completed() -> None:
    svc = _service(_State({"type": "create_agent", "status": "awaiting_confirm"}))
    with (
        patch.object(svc, "_create_agent", new=AsyncMock(return_value=_agent(False))),
        patch("app.services.execution_outcome.finalize_execution_outcome") as finalize,
        patch.object(svc, "_record_learning_outcome", new=AsyncMock()) as learn,
    ):
        _run(svc)
    assert finalize.call_args.kwargs["status"] == "verification_inconclusive"
    learn.assert_not_called()


def test_finalize_failure_never_turns_a_created_entity_into_an_error() -> None:
    svc = _service(_State({"type": "create_agent", "status": "awaiting_confirm"}))
    with (
        patch.object(svc, "_create_agent", new=AsyncMock(return_value=_agent(True))),
        patch("app.services.execution_outcome.finalize_execution_outcome", side_effect=RuntimeError("fanout down")),
        patch.object(svc, "_record_learning_outcome", new=AsyncMock()),
    ):
        result = _run(svc)
    assert result.success is True


def test_reconfirm_after_execution_replays_instead_of_creating_again() -> None:
    state = _State({"type": "create_agent", "status": "awaiting_confirm"})
    svc = _service(state)
    created = AsyncMock(return_value=_agent(True))
    with (
        patch.object(svc, "_create_agent", created),
        patch("app.services.execution_outcome.finalize_execution_outcome"),
        patch.object(svc, "_record_learning_outcome", new=AsyncMock()),
    ):
        _run(svc)
        assert state.state["pending_task"]["status"] == "executed"
        second = _run(svc)
    assert created.call_count == 1
    assert second.structured and second.structured.get("replayed") is True


def test_in_flight_claim_blocks_a_second_run() -> None:
    from datetime import datetime, timezone

    state = _State(
        {"type": "create_agent", "status": "executing", "claimed_at": datetime.now(timezone.utc).isoformat()}
    )
    svc = _service(state)
    created = MagicMock()
    with patch.object(svc, "_create_agent", created):
        result = _run(svc)
    created.assert_not_called()
    assert result.error_code == "WRITE_IN_FLIGHT"


def test_workflow_run_is_finalized_by_the_runtime_only() -> None:
    svc = _service(_State({"type": "execute_workflow", "status": "awaiting_confirm"}))
    run = ExecutionResult(
        success=True, entity_type="workflow_run", entity_id="run-1", title="W", body="ran", outcome_verified=False
    )
    with (
        patch.object(svc, "_execute_workflow", new=AsyncMock(return_value=run)),
        patch("app.services.execution_outcome.finalize_execution_outcome") as finalize,
    ):
        _run(svc, "execute_workflow")
    finalize.assert_not_called()


@pytest.mark.parametrize(
    ("status", "success", "verified"),
    [
        ("completed", True, True),
        ("verification_inconclusive", True, False),
        ("partial_success", True, False),
        ("failed", False, False),
        ("running", True, False),
    ],
)
def test_workflow_report_reflects_real_run_status(status: str, success: bool, verified: bool) -> None:
    ok, proven, body = ces._workflow_run_report("W", status)
    assert (ok, proven) == (success, verified)
    if not verified:
        assert "finished, and every change" not in body


def test_read_back_detects_missing_and_mismatched_records() -> None:
    missing = ces._read_back_evidence(lambda: None, read_action="x", resource_id="1", field="name", expected="A")
    assert missing["verified"] is False and missing["detail"] == "record_not_found"
    renamed = ces._read_back_evidence(
        lambda: {"id": "1", "name": "B"}, read_action="x", resource_id="1", field="name", expected="A"
    )
    assert renamed["verified"] is False
    good = ces._read_back_evidence(
        lambda: {"id": "1", "name": "a"}, read_action="x", resource_id="1", field="name", expected="A"
    )
    assert good["verified"] is True
