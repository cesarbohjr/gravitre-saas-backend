"""Recovery worker must not cross tenants, replay writes, or lose unknown work."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.write_recovery_worker import process_due_write_recoveries
from app.services.write_recovery_service import RecoveryResult


def _service(rows):
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = rows
    return client


def test_worker_uses_original_tenant_and_connector_context():
    row = {"org_id": "org-a", "connector_id": "conn-a",
           "invoke_action": "hubspot.contacts.create",
           "idempotency_key": "claim-a", "recovery_lease_token": "lease-1", "original_args": {"email": "a@example.test"}}
    client = _service([row])
    ctx = SimpleNamespace(org_id="org-a", connector_id="conn-a", client=MagicMock())
    with patch("app.services.write_recovery_worker.recover_uncertain_write",
               return_value=RecoveryResult("completed", "found")) as recover:
        stats = process_due_write_recoveries(
            service_client=client, context_factory=lambda org, conn: ctx,
        )
    assert stats["completed"] == 1
    assert recover.call_args.kwargs["ctx"].client is client
    assert recover.call_args.kwargs["original_args"] == row["original_args"]


def test_worker_rejects_cross_tenant_context_before_readback():
    row = {"org_id": "org-a", "connector_id": "conn-a",
           "invoke_action": "hubspot.contacts.create",
           "idempotency_key": "claim-a", "recovery_lease_token": "lease-a",
           "original_args": {"email": "a@example.test"}}
    with patch("app.services.write_recovery_worker.recover_uncertain_write") as recover:
        stats = process_due_write_recoveries(
            service_client=_service([row]),
            context_factory=lambda org, conn: SimpleNamespace(
                org_id="org-b", connector_id=conn, client=MagicMock()),
        )
    assert stats["rejected"] == 1
    recover.assert_not_called()


def test_worker_preserves_unknown_without_retrying():
    row = {"org_id": "org-a", "connector_id": "conn-a",
           "invoke_action": "hubspot.contacts.create",
           "idempotency_key": "claim-a", "recovery_lease_token": "lease-a",
           "original_args": {"email": "a@example.test"}}
    service = _service([row])
    with patch("app.services.write_recovery_worker.recover_uncertain_write",
               return_value=RecoveryResult("unknown", "no_readback")) as recover:
        stats = process_due_write_recoveries(
            service_client=service,
            context_factory=lambda org, conn: SimpleNamespace(
                org_id=org, connector_id=conn, client=MagicMock()),
        )
    assert stats["unknown"] == 1
    recover.assert_called_once()
    assert recover.call_args.kwargs["recovery_lease_token"] == "lease-a"
    assert service.rpc.call_args_list[-1].args[0] == "defer_leased_write_recovery"
    assert service.rpc.call_args_list[-1].args[1] == {
        "p_org_id": "org-a", "p_key": "claim-a", "p_lease_token": "lease-a",
    }


def test_scheduler_frozen_tool_context_recovers_without_mutating_credentials():
    """Actual scheduler ToolContext is frozen; the worker must not assign into it."""
    from app.services.tool_types import ToolContext

    row = {
        "org_id": "org-a", "connector_id": "conn-a",
        "invoke_action": "hubspot.contacts.create",
        "idempotency_key": "claim-a", "recovery_lease_token": "lease-a",
        "original_args": {"email": "a@example.test"},
    }
    service = _service([row])
    original_client = MagicMock()
    original = ToolContext(
        settings=SimpleNamespace(), client=original_client,
        org_id="org-a", actor_id="system:write-recovery",
        connector_id="conn-a",
    )
    with patch(
        "app.services.write_recovery_worker.recover_uncertain_write",
        return_value=RecoveryResult("completed", "verified"),
    ) as recover:
        stats = process_due_write_recoveries(
            service_client=service, context_factory=lambda org, connector: original,
        )
    assert stats == {
        "seen": 1, "completed": 1, "not_applied": 0,
        "unknown": 0, "rejected": 0, "error": 0,
    }
    recovered = recover.call_args.kwargs["ctx"]
    assert recovered is not original
    assert recovered.client is service
    assert original.client is original_client
    assert recovered.org_id == original.org_id
    assert recovered.connector_id == original.connector_id
    assert recover.call_args.kwargs["recovery_lease_token"] == "lease-a"


def test_queue_row_without_lease_is_not_given_to_provider_readback():
    row = {
        "org_id": "org-a", "connector_id": "conn-a",
        "invoke_action": "hubspot.contacts.create",
        "idempotency_key": "claim-a", "recovery_lease_token": None,
        "original_args": {"email": "a@example.test"},
    }
    client = _service([row])
    with patch("app.services.write_recovery_worker.recover_uncertain_write") as recover:
        with patch("app.services.write_recovery_worker.logger") as _log:
            context_factory = MagicMock()
            stats = process_due_write_recoveries(
                service_client=client, context_factory=context_factory,
            )
    assert stats["seen"] == 1
    assert stats["unknown"] == 1
    context_factory.assert_not_called()
    recover.assert_not_called()
