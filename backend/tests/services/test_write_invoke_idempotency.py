from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.tool_types import NormalizedResult, ToolContext
from app.services.write_invoke_idempotency import (
    build_write_idempotency_key,
    lookup_completed_write,
    record_completed_write,
)


def test_build_key_stable_for_same_chat_write():
    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="u1",
        conversation_id="conv-1",
    )
    params = {"pending_action_id": "pa-1", "email": "a@example.com"}
    k1, lid1 = build_write_idempotency_key(ctx, "gmail.messages.send", params)
    k2, lid2 = build_write_idempotency_key(ctx, "gmail.messages.send", params)
    assert k1 == k2 and lid1 == lid2
    assert k1.startswith("chat:")


def test_build_key_differs_for_workflow_lineage():
    base = dict(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="u1",
        run_id="run-1",
        step_id="step-1",
    )
    ctx_a = ToolContext(**base)
    ctx_b = ToolContext(**{**base, "step_id": "step-2"})
    ka, _ = build_write_idempotency_key(ctx_a, "slack.messages.post", {"channel": "C1"})
    kb, _ = build_write_idempotency_key(ctx_b, "slack.messages.post", {"channel": "C1"})
    assert ka != kb
    assert ka.startswith("invoke:")


def test_lookup_returns_cached_success():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {
            "status": "completed",
            "result": {
                "success": True,
                "action": "hubspot.contacts.update",
                "data": {"id": "1"},
            },
        }
    ]
    out = lookup_completed_write(client, org_id="org-1", idempotency_key="invoke:abc")
    assert out is not None and out.success and out.data["id"] == "1"


def test_record_completed_write_upserts():
    client = MagicMock()
    record_completed_write(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        invoke_action="hubspot.contacts.update",
        logical_action_id_value=None,
        result=NormalizedResult(success=True, action="hubspot.contacts.update", data={"id": "1"}),
    )
    client.table.assert_called_with("write_invoke_idempotency")
    client.table.return_value.upsert.assert_called_once()
