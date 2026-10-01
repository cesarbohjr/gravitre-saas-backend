from unittest.mock import MagicMock, patch

from app.services.write_success_verification import _terminalize_verified_chat_run


def _client_with_pending_run():
    client = MagicMock()
    result = MagicMock()
    result.data = [{
        "status": "running",
        "parameters": {
            "verification_lifecycle": {
                "required": True,
                "state": "verifying",
                "mode": "follow_up_entity_get",
                "verified": False,
            }
        },
    }]
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = result
    return client


def test_vendor_proof_is_the_only_success_terminalizer():
    client = _client_with_pending_run()
    with patch("app.workflows.repository.merge_run_parameters") as merge, patch(
        "app.services.execution_outcome.finalize_execution_outcome"
    ) as finalize:
        _terminalize_verified_chat_run(
            client=client,
            org_id="org-1",
            run_id="run-1",
            invoke_action="hubspot.contacts.create",
            verified=True,
            effect="created",
            detail="Vendor GET returned the created contact.",
            actor_id="user-1",
            conversation_id="conv-1",
            integration="hubspot",
        )
    assert merge.call_args.args[2]["verification_lifecycle"]["state"] == "verified"
    assert finalize.call_args.kwargs["status"] == "completed"
    assert finalize.call_args.kwargs["metadata"]["verification_verified"] is True


def test_failed_vendor_proof_cannot_leave_green_success():
    client = _client_with_pending_run()
    with patch("app.workflows.repository.merge_run_parameters"), patch(
        "app.services.execution_outcome.finalize_execution_outcome"
    ) as finalize:
        _terminalize_verified_chat_run(
            client=client,
            org_id="org-1",
            run_id="run-1",
            invoke_action="hubspot.contacts.create",
            verified=False,
            effect="not_found",
            detail="Vendor GET did not return the created contact.",
            actor_id="user-1",
            conversation_id="conv-1",
            integration="hubspot",
        )
    assert finalize.call_args.kwargs["status"] == "failed"
    assert finalize.call_args.kwargs["error_summary"]


def test_non_verification_run_is_not_terminalized():
    client = MagicMock()
    result = MagicMock()
    result.data = [{"status": "running", "parameters": {}}]
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = result
    with patch("app.services.execution_outcome.finalize_execution_outcome") as finalize:
        _terminalize_verified_chat_run(
            client=client,
            org_id="org-1",
            run_id="run-1",
            invoke_action="hubspot.contacts.create",
            verified=True,
            effect="created",
            detail="ok",
            actor_id="user-1",
            conversation_id="conv-1",
            integration="hubspot",
        )
    finalize.assert_not_called()
