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
