"""STA-108: human-in-the-loop interrupt channel."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.agent_interrupt_service import (
    AgentExecutionInterrupted,
    enforce_interrupt,
    request_interrupt,
)


def _chainable(data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [], error=None)
    return mock


def test_request_interrupt_inserts_pending_row():
    client = MagicMock()
    client.table.return_value = _chainable([])
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "int-1", "target_type": "agent_job", "target_id": "job-1", "signal": "cancel"}]
    )

    with patch("app.services.agent_interrupt_service.write_audit_event"):
        row = request_interrupt(
            client,
            org_id="org-1",
            target_type="agent_job",
            target_id="job-1",
            signal="cancel",
            actor_id="user-1",
        )
    assert row["signal"] == "cancel"
    assert row.get("applied_eagerly") is True


def test_request_interrupt_eagerly_cancels_workflow_run():
    client = MagicMock()
    client.table.return_value = _chainable([])
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "int-2",
                "target_type": "workflow_run",
                "target_id": "run-1",
                "signal": "cancel",
            }
        ]
    )

    with (
        patch("app.services.agent_interrupt_service.write_audit_event"),
        patch("app.services.execution_outcome.finalize_execution_outcome") as finalize,
    ):
        row = request_interrupt(
            client,
            org_id="org-1",
            target_type="workflow_run",
            target_id="run-1",
            signal="cancel",
            actor_id="user-1",
        )
    assert row.get("applied_eagerly") is True
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["status"] == "cancelled"
    assert finalize.call_args.kwargs["run_id"] == "run-1"


def test_enforce_interrupt_raises_for_pending_cancel():
    client = MagicMock()

    def table_side_effect(name: str):
        if name == "agent_execution_interrupts":
            return _chainable(
                [{"id": "int-1", "signal": "cancel", "target_type": "agent_job", "target_id": "job-1"}]
            )
        return _chainable()

    client.table.side_effect = table_side_effect
    with patch("app.services.agent_interrupt_service.write_audit_event"):
        with pytest.raises(AgentExecutionInterrupted) as exc:
            enforce_interrupt(client, "org-1", "agent_job", "job-1", actor_id="user-1")
    assert exc.value.signal == "cancel"
