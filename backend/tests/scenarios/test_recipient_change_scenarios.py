"""Changing who a staged or sent email goes to, on both surfaces.

Two conversations used to go wrong:

* After "Yes." had sent the email to Stephanie, "Send it to steph@work.example
  instead." started a new, empty email ("What should the email say?") and
  never said the first one had already gone to her old address.
* Before approving, "Send it to Mike instead." dropped the staged email and
  answered with a garbled request for "a specific target"; the "Yes." that
  followed sent nothing.

A sent email can't be unsent: Gravitre says so and offers the same email to
the new recipient, behind a fresh approval. A staged email is re-addressed by
name through the user's own Gmail correspondence and shown again for a yes.
All people, addresses and mail are invented fixtures.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.scenarios.conversation_harness import (
    BrainCall,
    Reply,
    ScenarioHarness,
    TurnResult,
)
from tests.scenarios.name_resolution_fixtures import mail

SURFACES = ("text", "voice")
SEND = "gmail.messages.send"
READS = {"gmail.messages.list", "gmail.messages.get"}
ME = "Me <me@gravitre.example>"
STEPHANIE = "stephanie@acme.example"
CHEN = "Mike Chen <mike.chen@acme.example>"
ROSS = "Mike Ross <mross@globex.example>"
SUBJECT = "Quick update"
BODY = "The proposal is ready for review"


def _spoken(address: str, surface: str) -> str:
    if surface != "voice":
        return address
    local, _, domain = address.partition("@")
    return f"{local.replace('.', ' dot ')} at {domain.replace('.', ' dot ')}"


def _model(call: BrainCall) -> Reply:
    """Sends what the user asked for; on a later "instead" it starts a new
    email with only the address it heard, as the live model did."""
    if call.after_tool:
        return Reply(text="Done.")
    name = next((t for t in call.tool_names if "gmail" in t and "send" in t), None)
    if not name:
        return Reply(text="What should the email say?")
    if "instead" in call.last_user.lower():
        return Reply(tool_calls=[(name, {"to": "steph@work.example"})])
    return Reply(tool_calls=[(name, {"to": STEPHANIE, "subject": SUBJECT, "body": BODY})])


def _sends(turn: TurnResult) -> list[Any]:
    return [c for c in turn.connector_calls if c.action == SEND]


def _args(turn: TurnResult) -> dict[str, Any]:
    return dict(((turn.pending_task or {}).get("params") or {}).get("args") or {})


def _status(turn: TurnResult) -> str:
    return str((turn.pending_task or {}).get("status") or "")


def _binding(turn: TurnResult) -> str:
    return str(((turn.pending_task or {}).get("params") or {}).get("approval_action_id") or "")


def _gmail(h: ScenarioHarness, *people: str) -> None:
    h.connected.append("gmail")
    h.connectors.mailbox += [mail(i, p, ME) for i, p in enumerate(people, start=1)]


async def _staged(conv) -> TurnResult:
    turn = await conv.say(
        f"Send an email to {STEPHANIE} on Gmail saying the proposal is ready for review, subject {SUBJECT}.",
        _model,
    )
    assert _status(turn) == "awaiting_confirm", turn.text
    assert not _sends(turn)
    return turn


async def _sent(conv) -> TurnResult:
    await _staged(conv)
    sent = await conv.say("Yes.", _model)
    sends = _sends(sent)
    assert len(sends) == 1 and sends[0].params["to"] == STEPHANIE
    return sent


def _assert_sends_once(turn: TurnResult, to: str) -> None:
    sends = _sends(turn)
    assert len(sends) == 1, [c.params for c in sends]
    assert sends[0].params["to"] == to
    assert sends[0].params["subject"] == SUBJECT
    assert sends[0].params["body"].rstrip(".") == BODY


# --- OD-1: a new recipient after the email went out -------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_a_new_address_after_the_send_says_it_already_went_and_offers_a_resend(surface: str) -> None:
    with ScenarioHarness() as h:
        _gmail(h)
        conv = h.conversation(surface)
        await _sent(conv)

        offer = await conv.say("Send it to steph@work.example instead.", _model)
        assert not _sends(offer), "a second email went out without a new approval"
        assert "What should the email say" not in offer.text
        assert f"That email already went to {_spoken(STEPHANIE, surface)}, and I can't unsend it." in offer.text
        assert "I can send the same email to the new address." in offer.text
        assert _spoken("steph@work.example", surface) in offer.text  # the user approves the address
        assert _status(offer) == "awaiting_confirm"
        args = _args(offer)
        assert args["to"] == "steph@work.example"
        assert args["subject"] == SUBJECT and args["body"].rstrip(".") == BODY
        assert "pending" not in offer.text.lower() and "approval_action" not in offer.text

        resent = await conv.say("Yes.", _model)
        _assert_sends_once(resent, "steph@work.example")


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_declining_the_resend_sends_nothing(surface: str) -> None:
    with ScenarioHarness() as h:
        _gmail(h)
        conv = h.conversation(surface)
        await _sent(conv)
        offer = await conv.say("Send it to steph@work.example instead.", _model)
        assert _status(offer) == "awaiting_confirm"

        declined = await conv.say("No", "Okay.")
        assert not _sends(declined)
        assert _status(declined) != "awaiting_confirm"
        later = await conv.say("Yes.", "Okay.")
        assert not _sends(later), "a declined resend went out on a later yes"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_a_new_name_after_the_send_is_looked_up_then_offered(surface: str) -> None:
    with ScenarioHarness() as h:
        _gmail(h, CHEN)
        conv = h.conversation(surface)
        await _sent(conv)

        offer = await conv.say("Send it to Mike instead.", _model)
        assert all(c.action in READS for c in offer.connector_calls), "the lookup wrote something"
        assert f"That email already went to {_spoken(STEPHANIE, surface)}, and I can't unsend it." in offer.text
        assert "I can send the same email to Mike Chen." in offer.text
        assert _spoken("mike.chen@acme.example", surface) in offer.text
        assert _args(offer)["to"] == "mike.chen@acme.example"
        assert _status(offer) == "awaiting_confirm"

        resent = await conv.say("Yes.", _model)
        _assert_sends_once(resent, "mike.chen@acme.example")


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_two_matches_after_the_send_ask_then_offer_the_chosen_one(surface: str) -> None:
    with ScenarioHarness() as h:
        _gmail(h, CHEN, ROSS)
        conv = h.conversation(surface)
        await _sent(conv)

        asked = await conv.say("Send it to Mike instead.", _model)
        assert asked.text == (
            f"That email already went to {_spoken(STEPHANIE, surface)}, and I can't unsend it. "
            "I found two Mikes: Mike Chen and Mike Ross. Which one?"
        )
        assert not _sends(asked)

        chosen = await conv.say("Mike Chen", _model)
        assert chosen.text.startswith("Got it, Mike Chen."), chosen.text
        assert _spoken("mike.chen@acme.example", surface) in chosen.text
        assert not _sends(chosen)

        resent = await conv.say("Yes.", _model)
        _assert_sends_once(resent, "mike.chen@acme.example")


# --- OD-2: a new recipient by name before approving -------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize(
    "change",
    ["Send it to Mike instead.", "Make it go to Mike.", "Change the recipient to Mike Chen."],
)
async def test_one_match_readdresses_the_staged_email(surface: str, change: str) -> None:
    with ScenarioHarness() as h:
        _gmail(h, CHEN)
        conv = h.conversation(surface)
        first = await _staged(conv)

        changed = await conv.say(change, _model)
        assert all(c.action in READS for c in changed.connector_calls), "the lookup wrote something"
        assert "specific target" not in changed.text
        assert changed.text.startswith("Got it, I changed the recipient to Mike Chen."), changed.text
        assert _spoken("mike.chen@acme.example", surface) in changed.text  # the user approves the address
        assert _status(changed) == "awaiting_confirm"
        args = _args(changed)
        assert args["to"] == "mike.chen@acme.example"
        assert args["subject"] == SUBJECT
        assert _binding(changed) and _binding(changed) != _binding(first), "the old approval still applies"

        sent = await conv.say("Yes.", _model)
        _assert_sends_once(sent, "mike.chen@acme.example")


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_two_matches_ask_which_one_then_show_the_approval_again(surface: str) -> None:
    with ScenarioHarness() as h:
        _gmail(h, CHEN, ROSS)
        conv = h.conversation(surface)
        await _staged(conv)

        asked = await conv.say("Send it to Mike instead.", _model)
        assert asked.text == "I found two Mikes: Mike Chen and Mike Ross. Which one?"
        assert not _sends(asked)
        assert _status(asked) == "awaiting_params", "an ambiguous change left the old recipient approvable"
        args = _args(asked)
        assert "to" not in args and args["subject"] == SUBJECT, "the draft was discarded"

        unsure = await conv.say("Yes.", _model)
        assert not _sends(unsure), "a yes before choosing sent the email"

        chosen = await conv.say("Mike Ross", "Okay.")
        assert not _sends(chosen)
        assert chosen.text.startswith("Got it, I changed the recipient to Mike Ross."), chosen.text
        assert _spoken("mross@globex.example", surface) in chosen.text
        assert _status(chosen) == "awaiting_confirm"

        sent = await conv.say("Yes.", _model)
        _assert_sends_once(sent, "mross@globex.example")


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_no_match_asks_for_the_address_and_keeps_the_draft(surface: str) -> None:
    with ScenarioHarness() as h:
        _gmail(h, CHEN)
        conv = h.conversation(surface)
        await _staged(conv)

        missing = await conv.say("Send it to Jordan instead.", _model)
        assert missing.text.startswith("I couldn't find Jordan in this mailbox."), missing.text
        assert all(c.action in READS for c in missing.connector_calls), "nothing may be written"
        args = _args(missing)
        assert "to" not in args and args["subject"] == SUBJECT
        assert _status(missing) == "awaiting_params"

        given = await conv.say("It's jordan@acme.example", "Okay.")
        assert not _sends(given)
        assert _args(given)["to"] == "jordan@acme.example"
        assert _status(given) == "awaiting_confirm"

        sent = await conv.say("Yes.", _model)
        _assert_sends_once(sent, "jordan@acme.example")


# --- reading the change -----------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Send it to Mike instead.", ("name", "Mike")),
        ("Actually, make it go to Mike", ("name", "Mike")),
        ("Change the recipient to Mike Chen.", ("name", "Mike Chen")),
        ("Can you send it to Mike Chen instead?", ("name", "Mike Chen")),
        ("Send it to steph@work.example instead.", ("address", "steph@work.example")),
        ("Send it to her work address", None),
        ("Make the subject Weekly update", None),
        ("Yes, send it.", None),
        ("Send it to the team", None),
    ],
)
def test_parse_recipient_change(message: str, expected: tuple[str, str] | None) -> None:
    from app.services.pending_write_revision import parse_recipient_change

    assert parse_recipient_change(message) == expected
