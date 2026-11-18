"""Recovery never resends writes and only settles uncertain tenant-owned claims."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.outcome_reconciliation import ReconciliationResult
from app.services.write_recovery_service import recover_uncertain_write


def _ctx(status="uncertain", action="hubspot.contacts.create"):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"status": status, "invoke_action": action}
    ]
    client.rpc.return_value.execute.return_value.data = {"outcome": "reconciled"}
    return SimpleNamespace(client=client, org_id="org-1", connector_id="connector-1")


def _recover(ctx):
    return recover_uncertain_write(
        ctx=ctx, idempotency_key="chat:key",
        invoke_action="hubspot.contacts.create", original_args={"email": "a@example.test"},
    )


def test_applied_provider_effect_is_persisted_without_write_dispatch():
    ctx = _ctx()
    with patch("app.services.write_recovery_service.reconcile_uncertain_write",
               return_value=ReconciliationResult("applied", "found_by_email", "contact-1",
                                                 evidence={"verified": True})) as readback:
        outcome = _recover(ctx)
    assert outcome.state == "completed"
    readback.assert_called_once()
    args = ctx.client.rpc.call_args.args
    assert args[0] == "reconcile_write_invoke_idempotency"
    assert args[1]["p_status"] == "completed"
    assert args[1]["p_result"]["verification"]["state"] == "applied"


def test_unknown_outcome_stays_blocked_without_database_transition():
    ctx = _ctx()
    with patch("app.services.write_recovery_service.reconcile_uncertain_write",
               return_value=ReconciliationResult("unknown", "no_lookup_action")):
        assert _recover(ctx).state == "unknown"
    ctx.client.rpc.assert_not_called()


def test_wrong_action_or_non_uncertain_claim_never_reads_provider():
    for status, action in [("completed", "hubspot.contacts.create"), ("uncertain", "slack.post_message")]:
        ctx = _ctx(status, action)
        with patch("app.services.write_recovery_service.reconcile_uncertain_write") as readback:
            assert _recover(ctx).state == "rejected"
            readback.assert_not_called()
        ctx.client.rpc.assert_not_called()


def test_authoritative_absence_is_recorded_as_failed_not_replayed():
    ctx = _ctx()
    with patch("app.services.write_recovery_service.reconcile_uncertain_write",
               return_value=ReconciliationResult("not_applied", "no_record_with_email")):
        assert _recover(ctx).state == "not_applied"
    assert ctx.client.rpc.call_args.args[1]["p_status"] == "failed"


def test_concurrent_recovery_state_change_is_not_reported_as_success():
    ctx = _ctx()
    ctx.client.rpc.return_value.execute.return_value.data = {"outcome": "rejected", "reason": "not_uncertain"}
    with patch("app.services.write_recovery_service.reconcile_uncertain_write",
               return_value=ReconciliationResult("applied", "found_by_email",
                                                 evidence={"verified": True})):
        assert _recover(ctx).state == "rejected"
