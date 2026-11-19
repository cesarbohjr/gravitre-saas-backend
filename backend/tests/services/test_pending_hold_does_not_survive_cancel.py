"""Regression guard: a cancelled approval must not follow the user around.

Written after a false alarm, which is worth stating plainly because the shape of
the mistake is the thing worth guarding against. A live probe appeared to show a
"Create list" hold surviving a `cancel` into a brand-new conversation. It had
not. The probe opened a fresh conversation per turn, so the `cancel` landed on a
conversation that never had a hold, while a later turn created one of its own —
and `format_pending_meta_answer` says "I **still** have X waiting for approval"
even on first mention, which made a new hold read like a surviving one.

The premise was wrong, but the invariants it assumed are real and worth pinning:

  1. `cancel` on an active hold classifies as reject, not modify or ambiguous.
  2. Pending state is conversation-scoped, so a new conversation cannot inherit
     a hold from an earlier one.
  3. Terminal approval state is cleared. A completed write receipt stays readable
     without becoming an active approval.

Live counterpart: `scripts/verify-pending-cancel-clears-hold.py`, PASS at tip
`db928881`.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings
from app.services.conversation_state_service import (
    DEFAULT_TASK_STATE,
    ConversationStateService,
)
from app.services.conversation_turn_controller import (
    prepare_conversation_turn,
    terminal_task_cleanup,
)
from app.services.pending_reply_classifier import (
    build_pending_snapshot,
    classify_pending_reply_fast,
    has_pending_family,
    is_clear_pending_cancel_intent,
)
from tests.services.fake_supabase_db import FakeSupabaseDB


def _awaiting_confirm_state() -> dict[str, Any]:
    """The exact shape production wrote, read back from the live artifact.

    `status` genuinely appears at both levels: `build_pending_snapshot` reads the
    top-level one, and a fixture that only nests it under `params` produces a
    snapshot with no status at all — which would make this whole file pass
    against a hold the code does not consider pending.
    """
    return {
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_confirm",
            "params": {
                "label": "Create list",
                "status": "awaiting_confirm",
                "tool_name": "hubspot_lists_create",
                "invoke_action": "hubspot.lists.create",
                "integration": "hubspot",
                "destructive": True,
                "requires_approval": True,
                "args": {"name": "ZZ-CancelHold-Probe", "object_type_id": "0-1"},
            },
        }
    }


@pytest.mark.parametrize("phrase", ["cancel", "Cancel.", "never mind", "drop it", "forget it"])
def test_cancel_phrasings_reject_an_awaiting_confirm_hold(phrase: str) -> None:
    snap = build_pending_snapshot(_awaiting_confirm_state())
    assert snap.status == "awaiting_confirm"
    assert is_clear_pending_cancel_intent(phrase) is True, phrase
    assert classify_pending_reply_fast(phrase, snap) == "reject", phrase


def test_a_destructive_hold_is_recognised_as_pending_at_all() -> None:
    """If has_pending_family were False the cancel path would never be consulted."""
    assert has_pending_family(_awaiting_confirm_state()) is True
    assert has_pending_family({"pending_task": None}) is False


def test_pending_state_is_conversation_scoped_so_a_new_conversation_starts_clean() -> None:
    """The invariant that makes the original report impossible as described.

    `task_state` is stored on the `conversations` row. A hold therefore cannot be
    org-scoped, and a newly created conversation cannot inherit one. If this
    default ever gains a non-null pending_task, a cancelled approval really could
    reappear somewhere the user never approved it.
    """
    assert DEFAULT_TASK_STATE.get("pending_task") is None
    snap = build_pending_snapshot(dict(DEFAULT_TASK_STATE))
    assert snap.status in ("", None) or not snap.status
    assert has_pending_family(dict(DEFAULT_TASK_STATE)) is False


@pytest.mark.parametrize(
    ("terminal_status", "keep_receipt"),
    [("cancelled", False), ("completed", False), ("failed", False), ("completed", True)],
)
@pytest.mark.asyncio
async def test_terminal_approval_cannot_be_confirmed_on_the_next_turn(
    mock_settings: Settings, terminal_status: str, keep_receipt: bool,
) -> None:
    pending = {"status": terminal_status, "params": {"label": "Create list"}}
    if keep_receipt:
        pending = {
            "type": "connector_action",
            "status": terminal_status,
            "params": {
                "kind": "write",
                "invoke_action": "gmail.messages.send",
                "args": {"to": "pat@example.test"},
            },
            "result": {"success": True},
        }
    state = {"pending_task": pending, "current_plan": {"goal": "Create list"}}
    db = FakeSupabaseDB()
    db.tables["conversations"] = [{"id": "conv-1", "org_id": "org-1", "task_state": state}]

    turn = await prepare_conversation_turn(
        message="yes",
        org_id="org-1",
        conversation_id="conv-1",
        task_state=state,
        client=db,
        settings=mock_settings,
    )

    stored = db.tables["conversations"][0]["task_state"]
    assert stored["pending_task"] == (pending if keep_receipt else None)
    assert stored["current_plan"] is None
    assert not has_pending_family(stored)
    assert not turn.pending_confirm
    assert turn.pending_reply_intent is None


@pytest.mark.asyncio
async def test_locked_terminal_cleanup_preserves_a_newer_approval(mock_settings: Settings) -> None:
    db = FakeSupabaseDB()
    db.tables["conversations"] = [{
        "id": "conv-1",
        "org_id": "org-1",
        "task_state": {"pending_task": {"status": "cancelled"}},
    }]
    service = ConversationStateService(mock_settings)
    stale = await service.get_task_state("conv-1", "org-1", client=db)
    assert terminal_task_cleanup(stale) is not None

    await service.update_task_state("conv-1", "org-1", _awaiting_confirm_state(), client=db)
    current = db.snapshot()
    await service.update_task_state_from("conv-1", "org-1", terminal_task_cleanup, client=db)

    assert db.snapshot() == current
    assert has_pending_family(current["conversations"][0]["task_state"])
