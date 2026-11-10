from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.tool_types import NormalizedResult, ToolContext
from app.services.write_invoke_idempotency import (
    WriteClaimResult,
    build_write_idempotency_key,
    claim_write_invoke,
    finalize_write_invoke,
)


def test_build_key_differs_by_turn_id():
    base = dict(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="u1",
        conversation_id="conv-1",
    )
    ctx_a = ToolContext(**base, turn_id="turn-1")
    ctx_b = ToolContext(**{**base, "turn_id": "turn-2"})
    params = {"pending_action_id": "pa-1", "email": "a@example.com"}
    ka, _ = build_write_idempotency_key(ctx_a, "gmail.messages.send", params)
    kb, _ = build_write_idempotency_key(ctx_b, "gmail.messages.send", params)
    assert ka != kb


def test_build_key_nonce_allows_intentional_repeat():
    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="u1",
        conversation_id="conv-1",
        turn_id="turn-1",
    )
    params = {"pending_action_id": "pa-1", "_write_idempotency_nonce": "second-send"}
    k1, _ = build_write_idempotency_key(ctx, "gmail.messages.send", params)
    k2, _ = build_write_idempotency_key(
        ctx, "gmail.messages.send", {**params, "_write_idempotency_nonce": "third-send"}
    )
    assert k1 != k2


def test_claim_replay_from_rpc():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = {
        "outcome": "replay",
        "status": "completed",
        "result": {"success": True, "action": "hubspot.contacts.update", "data": {"id": "1"}},
    }
    out = claim_write_invoke(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        invoke_action="hubspot.contacts.update",
        logical_action_id_value=None,
    )
    assert isinstance(out, WriteClaimResult)
    assert out.outcome == "replay" and out.replay is not None and out.replay.success


def test_finalize_uses_fenced_rpc():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = {"outcome": "finalized"}
    out = finalize_write_invoke(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        claim_token="11111111-1111-4111-8111-111111111111",
        status="completed",
        result=NormalizedResult(success=True, action="hubspot.contacts.update", data={"id": "1"}),
    )
    assert out.outcome == "finalized"
    client.rpc.assert_called_once()
    assert client.rpc.call_args[0][0] == "finalize_write_invoke_idempotency"


def test_finalize_rejects_missing_token():
    client = MagicMock()
    out = finalize_write_invoke(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        claim_token=None,
        status="failed",
    )
    assert out.outcome == "rejected"
    client.rpc.assert_not_called()


def test_claim_fails_closed_without_fencing_token():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = {
        "outcome": "claimed", "status": "in_progress", "claim_generation": 1,
    }
    out = claim_write_invoke(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        invoke_action="hubspot.contacts.update",
        logical_action_id_value=None,
    )
    assert out.outcome == "error"
    assert out.reason == "missing_claim_token"
    assert out.claim_token is None
    client.rpc.assert_called_once()


def test_queue_approval_id_is_stable_ledger_identity_and_separates_distinct_approvals():
    """Two intentional identical writes cannot share an approval's ledger key."""
    ctx = dict(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="requester-1",
        conversation_id="conv-1",
        write_idempotency_required=True,
    )
    params = {"email": "qa@example.invalid", "subject": "Approved", "body": "Fixture"}
    first = ToolContext(**ctx, turn_id="approval-1")
    second = ToolContext(**ctx, turn_id="approval-2")
    k1, logical1 = build_write_idempotency_key(first, "gmail.messages.send", params)
    replay, logical_replay = build_write_idempotency_key(first, "gmail.messages.send", dict(params))
    k2, logical2 = build_write_idempotency_key(second, "gmail.messages.send", params)
    assert k1.startswith("chat:") and k1 == replay
    assert logical1 == logical_replay
    assert k1 != k2 and logical1 != logical2


def test_queue_approved_unknown_write_classification_fails_closed():
    import pytest
    from app.services.tool_service import assert_queue_write_ledger_classified
    from app.services.tool_types import ToolValidationError

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="reviewer-1",
        write_idempotency_required=True,
    )
    with pytest.raises(ToolValidationError) as exc:
        assert_queue_write_ledger_classified(ctx, "qa.nonexistent_action")
    assert exc.value.code == "WRITE_LEDGER_CLASSIFICATION_REQUIRED"

    permissive_ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="reviewer-1",
    )
    assert_queue_write_ledger_classified(permissive_ctx, "qa.nonexistent_action") is None


def test_queued_approval_ledger_identity_is_tenant_and_arguments_bound():
    """Queued approvals must not alias across tenants or changed provider payloads."""
    base = {
        "settings": SimpleNamespace(),
        "client": MagicMock(),
        "actor_id": "requester-1",
        "conversation_id": "conv-1",
        "turn_id": "approval-1",
        "write_idempotency_required": True,
    }
    first = ToolContext(**base, org_id="org-one")
    foreign = ToolContext(**base, org_id="org-two")
    action = "hubspot.contacts.create"
    args = {"email": "pr611-qa@example.invalid", "firstname": "Original"}
    initial_key, initial_logical = build_write_idempotency_key(first, action, args)
    foreign_key, foreign_logical = build_write_idempotency_key(foreign, action, args)
    changed_key, changed_logical = build_write_idempotency_key(
        first, action, {**args, "firstname": "Tampered"}
    )
    assert initial_key != foreign_key
    assert initial_logical != foreign_logical
    assert initial_key != changed_key
    assert initial_logical != changed_logical


def test_canonical_ledger_claim_error_fails_closed():
    """A missing or unavailable ledger must not be silently treated as a claim."""
    client = MagicMock()
    client.rpc.side_effect = RuntimeError("write_invoke_idempotency unavailable")
    claim = claim_write_invoke(
        client,
        org_id="org-one",
        idempotency_key="chat:approval-1",
        invoke_action="hubspot.contacts.create",
        logical_action_id_value="logical-1",
    )
    assert claim.outcome == "error"
    assert claim.claim_token is None
    client.rpc.assert_called_once()
