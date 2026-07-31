"""Unit tests for Module A finalize_execution_outcome()."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.execution_outcome import (
    VerifiedOutputRef,
    finalize_execution_outcome,
    is_terminal_run_status,
)


class _Table:
    def __init__(self, name: str, store: dict[str, list]) -> None:
        self.name = name
        self.store = store
        self._payload: dict[str, Any] | None = None
        self._filters: list[tuple[str, Any]] = []

    def insert(self, payload: dict[str, Any]) -> "_Table":
        self._payload = dict(payload)
        return self

    def update(self, payload: dict[str, Any]) -> "_Table":
        self._payload = dict(payload)
        return self

    def select(self, *_cols: str) -> "_Table":
        return self

    def eq(self, key: str, value: Any) -> "_Table":
        self._filters.append((key, value))
        return self

    def limit(self, *_args: Any) -> "_Table":
        return self

    def execute(self) -> MagicMock:
        if self._payload is not None and self.name == "intelligence_outcome_events":
            self.store.setdefault(self.name, []).append(dict(self._payload))
        if self._payload is not None and self.name == "workflow_runs":
            self.store.setdefault(self.name, []).append(dict(self._payload))
        result = MagicMock()
        if self.name == "workflow_runs" and self._payload is None:
            result.data = [{"workflow_id": "wf-1"}]
        else:
            result.data = [dict(self._payload)] if self._payload else []
        return result


class _Client:
    def __init__(self) -> None:
        self.store: dict[str, list] = {}

    def table(self, name: str) -> _Table:
        return _Table(name, self.store)


def test_is_terminal_run_status() -> None:
    assert is_terminal_run_status("completed")
    assert is_terminal_run_status("failed")
    assert is_terminal_run_status("cancelled")
    assert is_terminal_run_status("partial_success")
    assert not is_terminal_run_status("running")
    assert not is_terminal_run_status("paused")


def test_finalize_skips_duplicate_terminal_fanout() -> None:
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {
            "status": "failed",
            "parameters": {"notification_emitted": True, "outcome_finalized": True},
        }
    ]
    with (
        patch("app.workflows.repository.update_run") as update_run,
        patch("app.services.notification_emitter.emit_notification") as emit_notification,
    ):
        result = finalize_execution_outcome(
            client,
            org_id="org-1",
            status="failed",
            source="chat_orch",
            actor_id="11111111-1111-1111-1111-111111111111",
            run_id="22222222-2222-2222-2222-222222222222",
            error_summary="duplicate",
        )

    update_run.assert_not_called()
    emit_notification.assert_not_called()
    assert result.fanout.get("idempotent_skip") is True


def test_finalize_failure_fanout() -> None:
    client = _Client()
    with (
        patch("app.workflows.repository.update_run") as update_run,
        patch("app.workflows.repository.emit_execute_failed") as emit_failed,
        patch("app.services.notification_emitter.emit_notification") as emit_notification,
        patch(
            "app.services.workflow_failure_prediction_service.correlate_observed_run_failure",
            return_value=True,
        ) as correlate,
    ):
        result = finalize_execution_outcome(
            client,
            org_id="org-1",
            status="failed",
            source="chat_orch",
            actor_id="11111111-1111-1111-1111-111111111111",
            run_id="22222222-2222-2222-2222-222222222222",
            workflow_id="33333333-3333-3333-3333-333333333333",
            error_summary="step blew up",
            verified_output=VerifiedOutputRef(
                summary="step blew up",
                result_url="/runs/22222222-2222-2222-2222-222222222222",
                entity_type="workflow_run",
                entity_id="22222222-2222-2222-2222-222222222222",
            ),
        )

    assert result.status == "failed"
    assert result.notification_event == "run_failed"
    assert result.audit_action == "workflow.execute.failed"
    assert result.learning_event == "workflow_failed"
    assert result.fanout["run_persisted"] is True
    assert result.fanout["audit_written"] is True
    assert result.fanout["notification_emitted"] is True
    assert result.fanout["learning_recorded"] is True
    assert result.fanout["failure_alert_correlated"] is True
    update_run.assert_called_once()
    emit_failed.assert_called_once()
    emit_notification.assert_called_once()
    assert emit_notification.call_args.kwargs["event_type"] == "run_failed"
    # Module D house title — callers cannot bypass with notification_title.
    assert emit_notification.call_args.kwargs["title"] == "Orchestration run failed"
    body = emit_notification.call_args.kwargs["body"]
    assert "Blocked." in body or "step blew up" in body
    correlate.assert_called_once()
    assert client.store.get("intelligence_outcome_events")


def test_finalize_success_does_not_correlate_failure_alert() -> None:
    client = _Client()
    with (
        patch("app.workflows.repository.update_run"),
        patch("app.workflows.repository.emit_execute_completed"),
        patch("app.services.notification_emitter.emit_notification") as emit_notification,
        patch(
            "app.services.workflow_failure_prediction_service.correlate_observed_run_failure"
        ) as correlate,
    ):
        result = finalize_execution_outcome(
            client,
            org_id="org-1",
            status="completed",
            source="api",
            actor_id="11111111-1111-1111-1111-111111111111",
            run_id="22222222-2222-2222-2222-222222222222",
            verified_output={"summary": "ok", "result_url": "/runs/x"},
        )

    assert result.notification_event == "run_completed"
    assert result.fanout["failure_alert_correlated"] is False
    correlate.assert_not_called()
    assert emit_notification.call_args.kwargs["event_type"] == "run_completed"


def test_finalize_rejects_non_terminal() -> None:
    client = _Client()
    with pytest.raises(ValueError, match="terminal"):
        finalize_execution_outcome(
            client,
            org_id="org-1",
            status="running",
            source="api",
            actor_id="u",
            run_id="r",
        )


def test_assistant_chat_without_run_still_notifies() -> None:
    client = _Client()
    with (
        patch("app.workflows.repository.update_run") as update_run,
        patch("app.workflows.audit.write_audit_event") as write_audit,
        patch("app.services.notification_emitter.emit_notification") as emit_notification,
    ):
        result = finalize_execution_outcome(
            client,
            org_id="org-1",
            status="failed",
            source="assistant_chat",
            actor_id="11111111-1111-1111-1111-111111111111",
            persist_run=False,
            error_summary="connector failed",
            verified_output=VerifiedOutputRef(
                summary="connector failed",
                result_url="/ai",
                entity_type="connector",
                entity_id="44444444-4444-4444-4444-444444444444",
                integration="slack",
            ),
            metadata={"conversation_id": "55555555-5555-5555-5555-555555555555"},
        )

    update_run.assert_not_called()
    write_audit.assert_called_once()
    emit_notification.assert_called_once()
    assert result.notification_event == "run_failed"
    assert emit_notification.call_args.kwargs["event_type"] == "run_failed"
