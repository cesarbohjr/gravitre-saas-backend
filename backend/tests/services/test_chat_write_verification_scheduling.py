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
    """Run the real chat finalize path; return the verification scheduler spy."""
    service = ChatConnectorExecutionService()
    scheduler = MagicMock()
    tool_ctx = MagicMock()
    tool_ctx.connector_id = "conn-1"
    tool_ctx.environment_name = "production"

    with patch(
        "app.workflows.repository.create_run", return_value={"id": "run-1"}
    ), patch("app.workflows.repository.create_step", MagicMock()), patch(
        "app.workflows.repository.update_step", MagicMock()
    ), patch(
        "app.services.execution_outcome.finalize_execution_outcome", MagicMock()
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
    return scheduler


def test_entity_get_write_from_chat_is_scheduled_for_verification():
    """hubspot.contacts.create declares follow_up_entity_get — chat must run it."""
    plan = _plan(
        "hubspot.contacts.create",
        "hubspot",
        {"properties": {"email": "a@b.co", "firstname": "A"}},
    )
    scheduler = _finalize(plan, _ok_result("hubspot"))

    scheduler.assert_called_once()
    kwargs = scheduler.call_args.kwargs
    assert kwargs["invoke_action"] == "hubspot.contacts.create"
    assert kwargs["run_id"] == "run-1"
    assert kwargs["ctx"] is not None


def test_field_assert_write_from_chat_passes_the_requested_value():
    """Without request_params the assert has nothing to compare against."""
    plan = _plan(
        "hubspot.deals.update_stage",
        "hubspot",
        {"deal_id": "42", "stage": "closedwon"},
    )
    scheduler = _finalize(plan, _ok_result("hubspot"))

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
    _finalize(plan, failed).assert_not_called()


def test_accepted_async_write_is_not_scheduled():
    """No declared read-back mode means no follow-up to schedule."""
    from app.services.write_success_verification import resolve_success_verification

    action = "slack.post_message"
    assert resolve_success_verification(action).mode == "accepted_async"

    plan = _plan(action, "slack", {"channel": "C1", "text": "hi"})
    _finalize(plan, _ok_result("slack")).assert_not_called()


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
