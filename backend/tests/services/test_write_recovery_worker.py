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
           "idempotency_key": "claim-a", "original_args": {"email": "a@example.test"}}
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
           "idempotency_key": "claim-a", "original_args": {"email": "a@example.test"}}
    with patch("app.services.write_recovery_worker.recover_uncertain_write",
               return_value=RecoveryResult("unknown", "no_readback")):
        stats = process_due_write_recoveries(
            service_client=_service([row]),
            context_factory=lambda org, conn: SimpleNamespace(
                org_id=org, connector_id=conn, client=MagicMock()),
        )
    assert stats["unknown"] == 1
