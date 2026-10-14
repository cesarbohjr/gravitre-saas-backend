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


def test_finalize_updates_row():
    client = MagicMock()
    finalize_write_invoke(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        status="completed",
        result=NormalizedResult(success=True, action="hubspot.contacts.update", data={"id": "1"}),
    )
    client.table.assert_called_with("write_invoke_idempotency")
    client.table.return_value.update.assert_called_once()
