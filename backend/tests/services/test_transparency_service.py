"""STA-112: EU AI Act agent decision transparency logs."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.transparency_service import (
    append_tool_invocation,
    build_input_context,
    build_transparency_export_bundle,
    create_decision_log,
    finalize_decision_log_from_run,
    list_decision_logs,
    record_human_override,
)


def _chainable(data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.gte.return_value = mock
    mock.lte.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=data or [], error=None)
    return mock


@patch("app.services.transparency_service.write_audit_event")
def test_create_decision_log_persists_row(mock_audit):
    client = MagicMock()
    log_table = _chainable(
        [
            {
                "id": "log-1",
                "org_id": "org-1",
                "created_at": "2026-06-08T00:00:00+00:00",
                "updated_at": "2026-06-08T00:00:00+00:00",
                "decision_source": "operator_auto_execute",
                "input_context": {"planTitle": "Test"},
                "model_info": {},
                "tools_invoked": [],
                "human_override": None,
                "outcome": {},
                "status": "in_progress",
            }
        ]
    )
    client.table.side_effect = lambda name: log_table if name == "agent_decision_transparency_logs" else _chainable([])

    result = create_decision_log(
        client,
        org_id="org-1",
        actor_id="user-1",
        decision_source="operator_auto_execute",
        input_context={"planTitle": "Test", "operatorEmail": "secret@example.com"},
    )
    assert result["id"] == "log-1"
    assert result["decisionSource"] == "operator_auto_execute"
    log_table.insert.assert_called_once()
    mock_audit.assert_called_once()


def test_build_input_context_includes_step_and_plan():
    ctx = build_input_context(
        operator={"id": "op-1", "name": "Ops"},
        stored_plan={"id": "plan-1", "title": "Plan", "summary": "Do things"},
        step={"id": "step-1", "step_type": "execute_workflow", "title": "Run", "explanation": {"executable": True}},
        session={"id": "sess-1"},
        execution_mode="auto_trusted_scopes",
    )
    assert ctx["planId"] == "plan-1"
    assert ctx["stepType"] == "execute_workflow"
    assert ctx["executionMode"] == "auto_trusted_scopes"


@patch("app.services.transparency_service.write_audit_event")
def test_append_tool_invocation_appends_to_array(mock_audit):
    client = MagicMock()
    existing = {
        "id": "log-1",
        "tools_invoked": [{"action": "hubspot.contacts.list", "success": True}],
    }
    log_table = _chainable([existing])
    log_table.update.return_value = log_table

    def table_side_effect(name: str):
        if name == "agent_decision_transparency_logs":
            return log_table
        return _chainable([])

    client.table.side_effect = table_side_effect
    append_tool_invocation(
        client,
        org_id="org-1",
        log_id="log-1",
        action="email.send",
        connector_id="conn-1",
        success=False,
        error_code="HIPAA_REQUIRED",
    )
    update_payload = log_table.update.call_args[0][0]
    assert len(update_payload["tools_invoked"]) == 2
    assert update_payload["tools_invoked"][1]["action"] == "email.send"
    mock_audit.assert_not_called()


@patch("app.services.transparency_service.update_decision_log")
def test_record_human_override_by_run_id(mock_update):
    client = MagicMock()
    log_table = _chainable([{"id": "log-1", "workflow_run_id": "run-1"}])
    client.table.side_effect = lambda name: log_table if name == "agent_decision_transparency_logs" else _chainable([])
    mock_update.return_value = {"id": "log-1"}

    record_human_override(
        client,
        org_id="org-1",
        actor_id="admin-1",
        decision="approved",
        workflow_run_id="run-1",
        comment="Looks good",
    )
    mock_update.assert_called_once()


@patch("app.services.transparency_service.update_decision_log")
def test_finalize_decision_log_from_run_maps_status(mock_update):
    client = MagicMock()
    mock_update.return_value = {"status": "completed"}
    result = finalize_decision_log_from_run(
        client,
        org_id="org-1",
        log_id="log-1",
        workflow_run_id="run-1",
        final_status="completed",
        errors=[],
    )
    assert result["status"] == "completed"
    mock_update.assert_called_once()


@patch("app.services.transparency_service.write_audit_event")
def test_build_export_bundle_includes_summary(mock_audit):
    client = MagicMock()
    logs = [
        {
            "id": "log-1",
            "created_at": "2026-06-08T00:00:00+00:00",
            "updated_at": "2026-06-08T00:00:00+00:00",
            "decision_source": "operator_auto_execute",
            "input_context": {},
            "model_info": {},
            "tools_invoked": [],
            "human_override": {"decision": "approved"},
            "outcome": {},
            "status": "completed",
        }
    ]
    log_table = _chainable(logs)
    client.table.side_effect = lambda name: log_table if name == "agent_decision_transparency_logs" else _chainable([])

    bundle = build_transparency_export_bundle(client, "org-1", actor_id="user-1")
    assert bundle["summary"]["decisionCount"] == 1
    assert bundle["summary"]["withHumanOverride"] == 1
    mock_audit.assert_called_once()


@patch("app.services.transparency_service._serialize_log")
def test_list_decision_logs_returns_serialized_rows(mock_serialize):
    client = MagicMock()
    log_table = _chainable([{"id": "log-1"}])
    client.table.side_effect = lambda name: log_table if name == "agent_decision_transparency_logs" else _chainable([])
    mock_serialize.return_value = {"id": "log-1", "status": "completed"}

    rows = list_decision_logs(client, "org-1", limit=10)
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
