"""Changing a staged email before approving it, on both surfaces.

"Actually, make the subject Weekly update" after the approval prompt used to
be answered with "still waiting for your approval", and the yes that followed
sent the old subject. The change must update the draft, show it again, and the
send must carry exactly the approved details, once.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.services.pending_write_revision import parse_field_edits, revise_pending_write
from tests.scenarios.conversation_harness import (
    BrainCall,
    Reply,
    ScenarioHarness,
    TurnResult,
)

SURFACES = ("text", "voice")
RECIPIENT = "stephanie@acme.example"
SEND = "gmail.messages.send"


def _one_shot_send(call: BrainCall) -> Reply:
    if call.after_tool:
        return Reply(text="Done.")
    name = next((t for t in call.tool_names if "gmail" in t and "send" in t), None)
    if not name:
        return Reply(text="What should the email say?")
    return Reply(
        tool_calls=[
            (name, {"to": RECIPIENT, "subject": "Quick update", "body": "The proposal is ready for review."})
        ]
    )


def _sends(turn: TurnResult) -> list[Any]:
    return [c for c in turn.connector_calls if c.action == SEND]


def _args(turn: TurnResult) -> dict[str, Any]:
    return dict(((turn.pending_task or {}).get("params") or {}).get("args") or {})


async def _staged(conv) -> TurnResult:
    turn = await conv.say(
        "Send an email to stephanie@acme.example on Gmail saying the proposal is ready "
        "for review, subject Quick update.",
        _one_shot_send,
    )
    assert (turn.pending_task or {}).get("status") == "awaiting_confirm"
    assert not _sends(turn)
    return turn


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_a_changed_subject_is_what_gets_sent(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        conv = h.conversation(surface)
        first = await _staged(conv)
        first_binding = ((first.pending_task or {}).get("params") or {}).get("approval_action_id")

        changed = await conv.say("Actually, make the subject Weekly update.", "Okay.")
        assert not _sends(changed)
        assert _args(changed)["subject"] == "Weekly update"
        assert "Got it, I changed the subject." in changed.text
        assert "Weekly update" in changed.text
        assert "still waiting" not in changed.text.lower()
        # A changed write is a new action: the earlier approval identity is gone.
        new_binding = ((changed.pending_task or {}).get("params") or {}).get("approval_action_id")
        assert new_binding and new_binding != first_binding

        sent = await conv.say("Yes, send it.", "Okay.")
        sends = _sends(sent)
        assert len(sends) == 1
        assert sends[0].params["subject"] == "Weekly update"
        assert sends[0].params["to"] == RECIPIENT
        assert "Weekly update" in sent.text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_changed_message_and_recipient_are_sent(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        conv = h.conversation(surface)
        await _staged(conv)

        body = await conv.say("Make it say we're on track for Friday.", "Okay.")
        assert _args(body)["body"] == "We're on track for Friday."
        assert "changed the message" in body.text

        to = await conv.say("Send it to steph@work.example instead.", "Okay.")
        assert _args(to)["to"] == "steph@work.example"
        assert "changed the recipient" in to.text
        assert not _sends(to)

        sent = await conv.say("Yes.", "Okay.")
        sends = _sends(sent)
        assert len(sends) == 1
        assert sends[0].params["to"] == "steph@work.example"
        assert sends[0].params["body"] == "We're on track for Friday."
        assert sends[0].params["subject"] == "Quick update"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Actually, make the subject Weekly update.", {"subject": "Weekly update"}),
        ("The subject should be Weekly update", {"subject": "Weekly update"}),
        ("Change the subject line to: Q3 numbers", {"subject": "Q3 numbers"}),
        ("Use Hello as the subject", {"subject": "Hello"}),
        ("Make it say we are on track", {"body": "We are on track."}),
        ("Change the message to: see you tomorrow", {"body": "See you tomorrow."}),
        ("Send it to steph@work.example instead", {"to": "steph@work.example"}),
        ("Thanks!", {}),
        ("Yes, send it.", {}),
        ("What's the subject?", {}),
        ("Cancel it.", {}),
        ("Use her work address", {}),
    ],
)
def test_field_edits(message: str, expected: dict[str, str]) -> None:
    assert parse_field_edits(message, invoke_action=SEND) == expected


def test_only_email_sends_are_revised_by_field_edits() -> None:
    assert parse_field_edits("Make the subject Hi", invoke_action="slack.chat.post_message") == {}


def _state(status: str, **pending_extra: Any) -> dict[str, Any]:
    from app.services.approval_action_binding import bind_plan_dict

    params = bind_plan_dict(
        {
            "tool_name": "gmail_messages_send",
            "invoke_action": SEND,
            "integration": "gmail",
            "kind": "write",
            "label": "Send email",
            "args": {"to": RECIPIENT, "subject": "Quick update", "body": "Hi."},
        }
    )
    return {
        "pending_task": {
            "id": "pending-1",
            "type": "connector_action",
            "status": status,
            "params": params,
            **pending_extra,
        }
    }


def test_revision_rebinds_the_approval() -> None:
    state = _state("awaiting_confirm")
    old = state["pending_task"]["params"]
    revised, edits = revise_pending_write("Make the subject Weekly update", state)  # type: ignore[misc]
    assert edits == {"subject": "Weekly update"}
    assert revised["params"]["args"]["subject"] == "Weekly update"
    assert revised["params"]["bound_args_digest"] != old["bound_args_digest"]
    assert revised["params"]["approval_action_id"] != old["approval_action_id"]
    assert "id" not in revised and revised["revision_of"] == "pending-1"


@pytest.mark.parametrize(
    "state",
    [
        _state("awaiting_admin_approval"),
        _state("awaiting_confirm", execution_claim_id="claim-1"),
        _state("completed"),
    ],
)
def test_claimed_queued_or_finished_writes_are_not_revised(state: dict[str, Any]) -> None:
    assert revise_pending_write("Make the subject Weekly update", state) is None


def test_the_same_value_is_not_a_revision() -> None:
    assert revise_pending_write("Make the subject Quick update", _state("awaiting_confirm")) is None
