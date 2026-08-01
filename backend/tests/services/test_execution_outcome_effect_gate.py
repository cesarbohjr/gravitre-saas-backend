"""finalize_execution_outcome coerces false COMPLETED via OutcomeEffect gate."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from app.services.execution_outcome import VerifiedOutputRef, finalize_execution_outcome


class _Table:
    def __init__(self, name: str, store: dict[str, list]) -> None:
        self.name = name
        self.store = store
        self._payload: dict[str, Any] | None = None

    def insert(self, payload: dict[str, Any]) -> "_Table":
        self._payload = dict(payload)
        return self

    def update(self, payload: dict[str, Any]) -> "_Table":
        self._payload = dict(payload)
        return self

    def select(self, *_cols: str) -> "_Table":
        return self

    def eq(self, *_args: Any) -> "_Table":
        return self

    def limit(self, *_args: Any) -> "_Table":
        return self

    def execute(self) -> MagicMock:
        if self._payload is not None and self.name == "intelligence_outcome_events":
            self.store.setdefault(self.name, []).append(dict(self._payload))
        result = MagicMock()
        if self.name == "workflow_runs" and self._payload is None:
            # Idempotency check: not yet finalized
            result.data = [{"status": "running", "parameters": {}, "workflow_id": "wf-1"}]
        else:
            result.data = [dict(self._payload)] if self._payload else [{"workflow_id": "wf-1"}]
        return result


class _Client:
    def __init__(self) -> None:
        self.store: dict[str, list] = {}

    def table(self, name: str) -> _Table:
        return _Table(name, self.store)


def test_finalize_coerces_completed_to_partial_when_outcome_effect_unknown() -> None:
    client = _Client()
    with (
        patch("app.workflows.repository.update_run") as update_run,
        patch("app.workflows.repository.merge_run_parameters") as merge_params,
        patch("app.workflows.repository.emit_execute_completed") as emit_completed,
        patch("app.services.notification_emitter.emit_notification") as emit_notification,
    ):
        result = finalize_execution_outcome(
            client,
            org_id="org-1",
            status="completed",
            source="assistant_chat",
            actor_id="11111111-1111-1111-1111-111111111111",
            run_id="22222222-2222-2222-2222-222222222222",
            verified_output=VerifiedOutputRef(
                summary="Create returned ok",
                result_url="/runs/22222222-2222-2222-2222-222222222222",
                entity_type="connector",
                entity_id="conn-1",
                integration="hubspot",
            ),
            metadata={
                "invoke_action": "hubspot.lists.create",
                "outcome_effect": "unknown",
                "integration": "hubspot",
            },
        )

    assert result.status == "partial_success"
    update_run.assert_called_once()
    assert update_run.call_args.kwargs["status"] == "partial_success"
    emit_completed.assert_called_once()
    # Notification uses coerced terminal (still run_completed for partial_success)
    emit_notification.assert_called_once()
    assert emit_notification.call_args.kwargs["event_type"] == "run_completed"
    # outcome_effect persisted onto run parameters
    merge_params.assert_called()
    merged = merge_params.call_args[0][2]
    assert merged.get("outcome_effect") == "unknown"


def test_finalize_keeps_completed_when_create_proven() -> None:
    client = _Client()
    with (
        patch("app.workflows.repository.update_run") as update_run,
        patch("app.workflows.repository.merge_run_parameters"),
        patch("app.workflows.repository.emit_execute_completed"),
        patch("app.services.notification_emitter.emit_notification"),
    ):
        result = finalize_execution_outcome(
            client,
            org_id="org-1",
            status="completed",
            source="assistant_chat",
            actor_id="11111111-1111-1111-1111-111111111111",
            run_id="22222222-2222-2222-2222-222222222222",
            verified_output=VerifiedOutputRef(
                summary="Created list",
                result_url="https://app.hubspot.com/lists/99",
                external_url="https://app.hubspot.com/lists/99",
                entity_type="list",
                entity_id="list-99",
                integration="hubspot",
            ),
            metadata={
                "invoke_action": "hubspot.lists.create",
                "structured": {"id": "list-99", "list_id": "list-99"},
            },
        )

    assert result.status == "completed"
    assert update_run.call_args.kwargs["status"] == "completed"


def test_finalize_apollo_already_existed_stays_partial_success() -> None:
    client = _Client()
    with (
        patch("app.workflows.repository.update_run") as update_run,
        patch("app.workflows.repository.merge_run_parameters"),
        patch("app.workflows.repository.emit_execute_completed"),
        patch("app.services.notification_emitter.emit_notification"),
    ):
        result = finalize_execution_outcome(
            client,
            org_id="org-1",
            status="partial_success",
            source="assistant_chat",
            actor_id="11111111-1111-1111-1111-111111111111",
            run_id="22222222-2222-2222-2222-222222222222",
            verified_output=VerifiedOutputRef(
                summary="Found existing contact list",
                result_url="/runs/22222222-2222-2222-2222-222222222222",
                entity_type="connector",
                entity_id="conn-1",
                integration="apollo",
            ),
            metadata={
                "invoke_action": "apollo.lists.create",
                "already_existed": True,
                "outcome_effect": "already_existed",
            },
        )

    assert result.status == "partial_success"
    assert update_run.call_args.kwargs["status"] == "partial_success"
