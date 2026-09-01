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
  3. A terminal pending is cleared on the next turn rather than lingering.

Live counterpart: `scripts/verify-pending-cancel-clears-hold.py`, PASS at tip
`db928881`.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.services.conversation_state_service import DEFAULT_TASK_STATE
from app.services.pending_reply_classifier import (
    build_pending_snapshot,
    classify_pending_reply_fast,
    has_pending_family,
    is_clear_pending_cancel_intent,
)


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


@pytest.mark.parametrize("terminal_status", ["cancelled", "completed", "failed"])
@pytest.mark.asyncio
async def test_a_terminal_pending_is_cleared_on_the_next_turn(
    monkeypatch: pytest.MonkeyPatch, terminal_status: str
) -> None:
    """A cancelled hold must not accept a later bare "yes".

    This is the durable half of cancel: not just that the reply is classified as
    reject, but that the record is actually cleared, so a stray confirmation on a
    later turn cannot resurrect a destructive write.
    """
    from app.services import conversation_state_service as css
    from app.services import conversation_turn_controller as ctc

    writes: list[dict[str, Any]] = []
    state = {
        "pending_task": {"status": terminal_status, "params": {"label": "Create list"}},
        "current_plan": {"goal": "Create list"},
    }

    class _FakeStateService:
        async def update_task_state(
            self, conversation_id: str, org_id: str, updates: dict[str, Any], *, client: Any = None
        ) -> None:
            writes.append(updates)
            state.update(updates)

        async def get_task_state(
            self, conversation_id: str, org_id: str, *, client: Any = None
        ) -> dict[str, Any]:
            return dict(state)

    # The controller imports this inside the function, so it must be patched at
    # the defining module rather than on the controller.
    monkeypatch.setattr(
        css, "get_conversation_state_service", lambda *_a, **_k: _FakeStateService()
    )
    assert ctc is not None

    await ctc.prepare_conversation_turn(
        message="yes",
        org_id="org-1",
        conversation_id="conv-1",
        task_state=state,
        persist=True,
    )

    cleared = [w for w in writes if "pending_task" in w and w["pending_task"] is None]
    assert cleared, (
        f"a {terminal_status} pending was not cleared; a later bare 'yes' could "
        "resurrect a destructive write"
    )
