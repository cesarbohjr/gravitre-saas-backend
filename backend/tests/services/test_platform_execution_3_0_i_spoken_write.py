"""3.0-I: spoken yes-wait is hold, not confirm; WRITE never invoked."""
from __future__ import annotations

import pytest

from app.services.intent_gateway import GatewayContext, evaluate_intent_gateway
from app.services.offered_action_continuation import is_confirm_utterance
from app.services.pending_reply_classifier import (
    build_pending_snapshot,
    classify_pending_reply_fast,
    has_pending_family,
)
from app.services.pipecat_voice.voice_tool_narration import will_execute_staged_connector_write
from app.services.react_write_gate import interrupt_blocks_write_commit
from app.services.reference_resolver import resolve_reference
from app.services.spoken_write_approval import classify_spoken_write_approval


PENDING = {
    "pending_task": {
        "id": "pa-write-1",
        "type": "connector_action",
        "status": "awaiting_confirm",
        "invoke_action": "gmail.messages.send",
    }
}


def test_yes_wait_is_hold_commit_not_confirm() -> None:
    spoken = classify_spoken_write_approval("yes wait", task_state=PENDING)
    assert spoken.decision == "hold_commit"
    assert spoken.invoke_allowed is False
    assert spoken.pending_action_id == "pa-write-1"
    assert spoken.as_trace()["provider_invoked"] is False

    ref = resolve_reference("yes wait", PENDING)
    assert ref.kind == "hold_commit"
    assert ref.matched is True

    yes = classify_spoken_write_approval("yes", task_state=PENDING)
    assert yes.decision == "confirm"
    assert yes.invoke_allowed is True
    assert yes.pending_action_id == "pa-write-1"


def test_mismatched_pending_action_does_not_confirm() -> None:
    spoken = classify_spoken_write_approval(
        "yes",
        task_state=PENDING,
        expected_pending_id="other-id",
    )
    assert spoken.invoke_allowed is False
    assert spoken.reason == "pending_action_mismatch"


def test_yes_wait_without_pending_is_still_hold_not_confirm() -> None:
    spoken = classify_spoken_write_approval("yes wait", task_state={})
    assert spoken.decision == "hold_commit"
    assert spoken.invoke_allowed is False


def test_hold_commit_fast_path_and_write_gate() -> None:
    snap = build_pending_snapshot(PENDING)
    assert classify_pending_reply_fast("yes wait", snap) == "hold_commit"
    assert classify_pending_reply_fast("yes", snap) == "confirm"
    assert is_confirm_utterance("yes wait") is False
    assert is_confirm_utterance("yes") is True
    assert interrupt_blocks_write_commit({"reason": "hold_commit"}) is True
    assert interrupt_blocks_write_commit(
        None, task_state={"last_pending_reply_intent": "hold_commit"}
    ) is True
    assert will_execute_staged_connector_write(PENDING, "yes wait") is False
    assert will_execute_staged_connector_write(PENDING, "yes") is True


def test_spoken_confirm_traces_bind_pending_and_never_invoke_on_hold() -> None:
    """3.0-I gate: spoken confirm traces (HTTP spoken_mode path, not VOICE_C mic)."""
    hold = classify_spoken_write_approval("yes wait", task_state=PENDING).as_trace()
    yes = classify_spoken_write_approval("yes", task_state=PENDING).as_trace()
    assert hold["decision"] == "hold_commit"
    assert hold["pending_action_id"] == "pa-write-1"
    assert hold["provider_invoked"] is False
    assert yes["decision"] == "confirm"
    assert yes["pending_action_id"] == "pa-write-1"
    assert yes["invoke_allowed"] is True


def test_pending_action_projection_is_pending_family() -> None:
    assert has_pending_family(
        {"pending_action": {"id": "pa-2", "status": "awaiting_user"}}
    ) is True


@pytest.mark.asyncio
async def test_gateway_shortcuts_yes_wait_before_kernel() -> None:
    decision = await evaluate_intent_gateway(
        GatewayContext(
            message="yes wait",
            spoken_mode=True,
            task_state=PENDING,
            org_id="org",
        )
    )
    assert decision.action == "shortcut"
    assert decision.candidate_id == "spoken_hold_commit"
    assert decision.answer is not None
    assert "on hold" in decision.answer.lower()
    assert "will not send" in decision.answer.lower()
    assert (decision.extras or {}).get("provider_invoked") is False
    assert (decision.extras or {}).get("spoken_write_decision") == "hold_commit"

