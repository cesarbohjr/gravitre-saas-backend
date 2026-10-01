"""Chat writes must actually schedule the verification their mode declares.

The bug this pins: `follow_up_entity_get` and `follow_up_field_assert` were wired
into the scheduler and proven against live HubSpot, but the chat path only ever
called the scheduler for *membership* writes whose inline check had already
failed. Every entity_get / field_assert write placed through chat was therefore
reported to the user at full confidence with nothing having verified it.

The earlier tests missed it because they called
`schedule_write_success_verification` directly. These drive
`_finalize_connector_outcome`, the function the chat surface actually runs.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    ConnectorActionPlan,
)
from app.services.conversational_execution_service import ExecutionResult


def _plan(action: str, integration: str, args: dict) -> ConnectorActionPlan:
    return ConnectorActionPlan(
        tool_name=action.replace(".", "_"),
        invoke_action=action,
        integration=integration,
        kind="write",
        label=f"Test {action}",
        args=args,
        requires_approval=True,
    )


def _ok_result(integration: str) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        entity_type="connector",
        entity_id="conn-1",
        connector_management_url="/connectors/conn-1",
        integration=integration,
        title="Done",
        body="Done.",
        task_label="Done",
    )


def _finalize(plan: ConnectorActionPlan, result: ExecutionResult):
    """Run the real chat finalize path and expose lifecycle write spies."""
    service = ChatConnectorExecutionService()
    scheduler = MagicMock()
    terminalizer = MagicMock()
    update_run = MagicMock()
    merge_params = MagicMock()
    tool_ctx = MagicMock()
    tool_ctx.connector_id = "conn-1"
    tool_ctx.environment_name = "production"

    with patch(
        "app.workflows.repository.create_run", return_value={"id": "run-1"}
    ), patch("app.workflows.repository.create_step", MagicMock()), patch(
        "app.workflows.repository.update_step", MagicMock()
    ), patch(
        "app.workflows.repository.update_run", update_run
    ), patch(
        "app.workflows.repository.merge_run_parameters", merge_params
    ), patch(
        "app.services.execution_outcome.finalize_execution_outcome", terminalizer
    ), patch(
        "app.services.write_success_verification.schedule_write_success_verification",
        scheduler,
    ):
        service._finalize_connector_outcome(
            MagicMock(),
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            plan=plan,
            result=result,
            tool_ctx=tool_ctx,
            connector_id="conn-1",
        )
    return {
        "scheduler": scheduler,
        "terminalizer": terminalizer,
        "update_run": update_run,
        "merge_params": merge_params,
    }


def test_entity_get_write_from_chat_is_scheduled_for_verification():
    """hubspot.contacts.create declares follow_up_entity_get — chat must run it."""
    plan = _plan(
        "hubspot.contacts.create",
        "hubspot",
        {"properties": {"email": "a@b.co", "firstname": "A"}},
    )
    spies = _finalize(plan, _ok_result("hubspot"))
    scheduler = spies["scheduler"]

    scheduler.assert_called_once()
    kwargs = scheduler.call_args.kwargs
    assert kwargs["invoke_action"] == "hubspot.contacts.create"
    assert kwargs["run_id"] == "run-1"
    assert kwargs["ctx"] is not None


def test_provider_acceptance_enters_verifying_before_terminal_success():
    plan = _plan(
        "hubspot.contacts.create",
        "hubspot",
        {"properties": {"email": "a@b.co", "firstname": "A"}},
    )
    spies = _finalize(plan, _ok_result("hubspot"))

    # Provider acceptance may update a run into VERIFYING, but it must not
    # emit terminal fanout until the source-of-record verifier returns.
    spies["scheduler"].assert_called_once()
    spies["terminalizer"].assert_not_called()
    assert spies["update_run"].call_count == 1
    assert spies["update_run"].call_args.args[1:] == ("run-1", "verifying")
    assert spies["merge_params"].call_args.args[1] == "run-1"
    pending = spies["merge_params"].call_args.args[2]
    assert pending["verification_status"] == "pending"
    assert pending["execution_lifecycle"] == "verifying"


def test_verifier_owns_completed_fanout_after_positive_source_proof():
    """Hard invariant: completed fanout happens only after source proof."""
    plan = _plan(
        "hubspot.contacts.create",
        "hubspot",
        {"properties": {"email": "a@b.co", "firstname": "A"}},
    )
    spies = _finalize(plan, _ok_result("hubspot"))
    spies["terminalizer"].assert_not_called()
    spies["scheduler"].assert_called_once()
    assert spies["update_run"].call_args.args[1:] == ("run-1", "verifying")

    from app.services.write_success_verification import _finalize_verified_write_run

    run_row = {
        "status": "verifying",
        "triggered_by": "user-1",
        "parameters": {
            "conversation_id": "conv-1",
            "verification_owns_terminal": True,
            "verification_status": "pending",
            "execution_lifecycle": "verifying",
            "integration": "hubspot",
            "label": "Test hubspot.contacts.create",
            "tool_name": "hubspot_contacts_create",
        },
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        run_row
    ]
    terminalizer = MagicMock()
    emit = MagicMock()
    with (
        patch("app.workflows.repository.merge_run_parameters"),
        patch(
            "app.services.execution_outcome.finalize_execution_outcome",
            terminalizer,
        ),
        patch("app.services.notification_emitter.emit_notification", emit),
    ):
        _finalize_verified_write_run(
            client=client,
            org_id="org-1",
            run_id="run-1",
            invoke_action="hubspot.contacts.create",
            verification_kind="entity_get",
            verification={
                "verified": True,
                "effect": "created",
                "detail": "follow_up_entity_get_confirmed",
                "entity_id": "42",
                "follow_up_attempted": True,
            },
        )

    terminalizer.assert_called_once()
    assert terminalizer.call_args.kwargs["status"] == "completed"
    emit.assert_not_called()


def test_positive_source_proof_persists_completed_and_emits_once():
    from app.services.write_success_verification import _finalize_verified_write_run

    run_row = {
        "status": "verifying",
        "triggered_by": "11111111-1111-1111-1111-111111111111",
        "parameters": {
            "conversation_id": "conv-1",
            "verification_owns_terminal": True,
            "verification_status": "pending",
            "execution_lifecycle": "verifying",
            "integration": "hubspot",
            "label": "Create contact",
        },
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        run_row
    ]
    update_run = MagicMock()
    emit = MagicMock()
    with (
        patch("app.workflows.repository.merge_run_parameters"),
        patch("app.workflows.repository.update_run", update_run),
        patch("app.services.notification_emitter.emit_notification", emit),
        patch(
            "app.services.execution_outcome._write_audit",
            return_value="workflow.execute.completed",
        ),
        patch(
            "app.services.execution_outcome._record_learning",
            return_value="workflow_executed",
        ),
        patch(
            "app.services.execution_outcome._record_play_actioned_result",
            return_value=False,
        ),
        patch(
            "app.services.execution_outcome._enqueue_failure_alert_correlation",
            return_value=False,
        ),
    ):
        _finalize_verified_write_run(
            client=client,
            org_id="org-1",
            run_id="run-1",
            invoke_action="hubspot.contacts.create",
            verification_kind="entity_get",
            verification={
                "verified": True,
                "effect": "created",
                "detail": "follow_up_entity_get_confirmed",
                "entity_id": "42",
                "follow_up_attempted": True,
            },
        )

    update_run.assert_called_once()
    assert update_run.call_args.kwargs["status"] == "completed"
    emit.assert_called_once()
    assert emit.call_args.kwargs["event_type"] == "run_completed"


def test_field_assert_write_from_chat_passes_the_requested_value():
    """Without request_params the assert has nothing to compare against."""
    plan = _plan(
        "hubspot.deals.update_stage",
        "hubspot",
        {"deal_id": "42", "stage": "closedwon"},
    )
    spies = _finalize(plan, _ok_result("hubspot"))
    scheduler = spies["scheduler"]

    scheduler.assert_called_once()
    kwargs = scheduler.call_args.kwargs
    assert kwargs["invoke_action"] == "hubspot.deals.update_stage"
    assert kwargs["request_params"] == {"deal_id": "42", "stage": "closedwon"}


def test_failed_write_is_not_scheduled_for_verification():
    """Nothing was written, so there is nothing to read back."""
    plan = _plan("hubspot.contacts.create", "hubspot", {"properties": {"email": "a@b.co"}})
    failed = ExecutionResult(
        success=False,
        entity_type="connector",
        entity_id="conn-1",
        connector_management_url="/connectors/conn-1",
        integration="hubspot",
        title="Failed",
        body="Vendor rejected the write.",
        task_label="Failed",
    )
    _finalize(plan, failed)["scheduler"].assert_not_called()


def test_accepted_async_write_is_not_scheduled():
    """No declared read-back mode means no follow-up to schedule."""
    from app.services.write_success_verification import resolve_success_verification

    action = "slack.post_message"
    assert resolve_success_verification(action).mode == "accepted_async"

    plan = _plan(action, "slack", {"channel": "C1", "text": "hi"})
    spies = _finalize(plan, _ok_result("slack"))
    spies["scheduler"].assert_not_called()
    spies["terminalizer"].assert_called_once()
    assert spies["terminalizer"].call_args.kwargs["status"] == "verification_inconclusive"


@pytest.mark.parametrize(
    "action",
    ["hubspot.contacts.create", "hubspot.deals.update_stage"],
)
def test_declared_followup_modes_are_recognised_as_needing_a_read(action: str):
    from app.services.write_success_verification import action_requires_followup_read

    assert action_requires_followup_read(action) is True


def test_accepted_async_actions_do_not_claim_a_followup_read():
    from app.services.write_success_verification import action_requires_followup_read

    assert action_requires_followup_read("slack.post_message") is False
    assert action_requires_followup_read("") is False
