"""3.0-I: spoken yes-wait is hold, not confirm; WRITE never invoked."""
from __future__ import annotations

from app.services.offered_action_continuation import is_confirm_utterance
from app.services.pending_reply_classifier import (
    build_pending_snapshot,
    classify_pending_reply_fast,
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
