"""Issue #535: a spoken wait must protect the actual provider commit boundary.

No provider is invoked. These exercise production begin_write_effect, not the
partial preflight/stop check previously used by the synthetic voice harness.
"""
from types import SimpleNamespace

import pytest

from app.services import voice_pause_gate
from app.services.tool_types import ToolValidationError
from app.services.turn_cancellation import TurnCancellation, bound_turn_cancellation
from app.services.voice_barge_in_write import (
    STATUS_COMPLETED,
    begin_write_effect,
    finish_write_effect,
    reset_write_effects_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_voice_write_state(monkeypatch):
    monkeypatch.setattr(
        "app.services.chat_turn_cancel_service.is_stop_requested",
        lambda *_a, **_kw: False,
    )
    voice_pause_gate.reset_for_tests()
    reset_write_effects_for_tests()
    yield
    voice_pause_gate.reset_for_tests()
    reset_write_effects_for_tests()


def _context():
    return SimpleNamespace(
        org_id="phase3-approval-org",
        conversation_id="phase3-approval-conversation",
        settings=SimpleNamespace(),
    )


@pytest.mark.asyncio
async def test_spoken_wait_blocks_email_at_final_commit_even_without_stop_marker():
    ctx = _context()
    assert voice_pause_gate.pause(ctx.org_id, ctx.conversation_id)
    assert voice_pause_gate.holds_writes(ctx.org_id, ctx.conversation_id)
    with pytest.raises(ToolValidationError, match="Paused before sending"):
        begin_write_effect(ctx, "gmail.send")


@pytest.mark.asyncio
async def test_unpaused_confirmed_write_may_reach_existing_provider_gate():
    ctx = _context()
    assert voice_pause_gate.pause(ctx.org_id, ctx.conversation_id)
    assert voice_pause_gate.resume(ctx.org_id, ctx.conversation_id)
    effect = begin_write_effect(ctx, "gmail.send")
    assert effect is not None and effect["status"] == "started"
    finish_write_effect(effect, STATUS_COMPLETED)
    assert effect["status"] == STATUS_COMPLETED


@pytest.mark.asyncio
async def test_cancelled_turn_still_blocks_write_after_conversation_marker_clears():
    ctx = _context()
    cancelled = TurnCancellation()
    cancelled.cancel("held_stop")
    with bound_turn_cancellation(cancelled):
        with pytest.raises(ToolValidationError, match="Stopped before sending"):
            begin_write_effect(ctx, "gmail.send")
