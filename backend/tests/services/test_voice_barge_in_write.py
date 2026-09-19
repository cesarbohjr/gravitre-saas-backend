"""3.0-C barge-in maps conversation stop onto WRITE commit block, not READs."""
from __future__ import annotations

from app.services.react_write_gate import WRITE_COMMIT_INTERRUPTED, block_react_write_execution
from app.services.tool_registry import get_tool_registry
from app.services.voice_barge_in_write import resolve_write_interrupt


def test_stop_requested_blocks_write_not_read():
    registry = get_tool_registry()
    live = resolve_write_interrupt(interrupt=None, stop_requested=True)
    assert live is not None
    assert live["reason"] == "barge_in"
    blocked = block_react_write_execution(
        "apollo_lists_create",
        {"name": "MSP"},
        registry,
        interrupt=live,
    )
    assert blocked is not None
    assert blocked["error_code"] == WRITE_COMMIT_INTERRUPTED
    assert blocked["provider_invoked"] is False
    read_ok = block_react_write_execution(
        "apollo_lists_list",
        {},
        registry,
        interrupt=live,
    )
    assert read_ok is None


def test_no_stop_leaves_write_gate_to_approval():
    live = resolve_write_interrupt(interrupt=None, stop_requested=False)
    assert live is None


def test_invoke_tool_blocks_write_when_conversation_stopped(monkeypatch):
    from types import SimpleNamespace

    from app.services.voice_barge_in_write import (
        conversation_stop_blocks_invoke,
        raise_if_barge_in_blocks_invoke,
    )
    from app.services.react_write_gate import WRITE_COMMIT_INTERRUPTED
    from app.services.tool_types import ToolValidationError

    monkeypatch.setattr(
        "app.services.chat_turn_cancel_service.is_stop_requested",
        lambda org, conv, settings=None: True,
    )
    ctx = SimpleNamespace(org_id="org-1", conversation_id="conv-1", settings=None)
    assert conversation_stop_blocks_invoke(ctx, "apollo.lists.create") is True
    assert conversation_stop_blocks_invoke(ctx, "apollo.lists.list") is False
    try:
        raise_if_barge_in_blocks_invoke(ctx, "apollo.lists.create")
        raise AssertionError("expected ToolValidationError")
    except ToolValidationError as exc:
        assert exc.code == WRITE_COMMIT_INTERRUPTED


def test_invoke_tool_allows_read_during_stop(monkeypatch):
    from types import SimpleNamespace

    from app.services.voice_barge_in_write import conversation_stop_blocks_invoke

    monkeypatch.setattr(
        "app.services.chat_turn_cancel_service.is_stop_requested",
        lambda org, conv, settings=None: True,
    )
    ctx = SimpleNamespace(org_id="org-1", conversation_id="conv-1", settings=None)
    assert conversation_stop_blocks_invoke(ctx, "hubspot.contacts.search") is False
