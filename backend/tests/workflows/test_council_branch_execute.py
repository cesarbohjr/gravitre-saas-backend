from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.workflows.execute import execute_workflow_steps


def test_execute_skips_steps_on_branch_mismatch():
    definition = {
        "steps": [
            {
                "id": "council_escalation",
                "name": "Council",
                "type": "noop",
                "config": {},
            },
            {
                "id": "marketing_enroll",
                "name": "Enroll",
                "type": "noop",
                "config": {"when_branch": "enroll"},
            },
            {
                "id": "marketing_nurture",
                "name": "Nurture",
                "type": "noop",
                "config": {"when_branch": "nurture"},
            },
        ]
    }
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "step-uuid"}])

    captured_updates: list[dict] = []

    def _capture_update(*, client, step_uuid, status, **kwargs):
        captured_updates.append({"step_uuid": step_uuid, "status": status, **kwargs})

    with patch("app.workflows.execute.get_handler") as get_handler, patch(
        "app.workflows.execute.create_step",
        side_effect=lambda **kwargs: {"id": f"uuid-{kwargs['step_id']}"},
    ), patch("app.workflows.execute.write_audit_event"), patch(
        "app.workflows.execute.emit_execute_step_completed"
    ), patch(
        "app.services.execution_outcome.finalize_execution_outcome"
    ), patch("app.workflows.execute.update_run"), patch(
        "app.workflows.execute.update_step", side_effect=_capture_update
    ), patch(
        "app.workflows.execute.get_run_with_steps",
        return_value={"steps": []},
    ):
        handler = MagicMock()
        handler.supports_execute = True
        handler.execute.return_value = {"branch": "enroll"}
        get_handler.return_value = handler

        status, _steps, errors, rate_limited = execute_workflow_steps(
            MagicMock(),
            "org-1",
            "user-1",
            "run-1",
            definition,
            {},
            client,
        )

    assert status == "completed"
    assert rate_limited is False
    assert not errors
    statuses = [row["status"] for row in captured_updates]
    assert statuses.count("skipped") == 1
    assert statuses.count("completed") == 2
