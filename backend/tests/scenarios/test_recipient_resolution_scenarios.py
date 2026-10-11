"""Finding "Stephanie" in the user's own mailbox, on both surfaces.

Before 2026-10-11 a name never reached a connector: the turn either asked
for an address or took whatever address the model wrote, which could be
invented. Now the recipient comes from what the user typed or from their
Gmail correspondence, and the lookup only ever reads.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.services.recipient_resolution import (
    RecipientCandidate,
    candidates_from_messages,
    extract_recipient_name,
    pick_candidate,
    resolution_from_candidates,
    resolution_question,
)
from tests.scenarios.conversation_harness import (
    BrainCall,
    Reply,
    ScenarioHarness,
    TurnResult,
)

SURFACES = ("text", "voice")
ME = "Me <me@gravitre.example>"
KHAN = "Stephanie Khan <stephanie.khan@acme.example>"
MILLER = "Stephanie Miller <smiller@globex.example>"
READS = {"gmail.messages.list", "gmail.messages.get"}


def _mail(i: int, frm: str, to: str, labels: tuple[str, ...] = ("INBOX",)) -> dict[str, Any]:
    return {"id": f"m{i}", "labelIds": list(labels), "headers": {"From": frm, "To": to}}


def _guessing_model(call: BrainCall) -> Reply:
    """A model that fills in an address nobody gave it."""
    if call.after_tool:
        return Reply(text="Done.")
    name = next((t for t in call.tool_names if "gmail" in t and "send" in t), None)
    if name:
        return Reply(tool_calls=[(name, {"to": "stephanie@invented.example"})])
    return Reply(text="Who should it go to?")


def _args(turn: TurnResult) -> dict[str, Any]:
    return dict(((turn.pending_task or {}).get("params") or {}).get("args") or {})


def _only_reads(turn: TurnResult) -> bool:
    return all(c.action in READS for c in turn.connector_calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_one_stephanie_is_found_and_the_send_goes_to_her(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        h.connectors.mailbox += [_mail(1, KHAN, ME), _mail(2, ME, KHAN, ("SENT",)), _mail(3, "Pat <pat@acme.example>", ME)]
        conv = h.conversation(surface)

        found = await conv.say("Send an email to Stephanie on Gmail", _guessing_model)
        assert found.text == "I found Stephanie Khan in your Gmail correspondence. What would you like to say?"
        assert _args(found)["to"] == "stephanie.khan@acme.example"
        assert "invented" not in str(found.task_state)
        assert _only_reads(found)

        await conv.say("Tell her the proposal is ready for review.", "Okay.")
        staged = await conv.say("The subject is Proposal.", "Okay.")
        assert (staged.pending_task or {}).get("status") == "awaiting_confirm", staged.text
        assert "stephanie.khan@acme.example" in staged.text  # the user approves the address

        sent = await conv.say("Yes, send it.", "Okay.")
        sends = [c for c in sent.connector_calls if c.action == "gmail.messages.send"]
        assert len(sends) == 1 and sends[0].params["to"] == "stephanie.khan@acme.example"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("pick", ["Khan", "The first one.", "Stephanie Khan"])
async def test_two_stephanies_are_asked_about_then_chosen(surface: str, pick: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        h.connectors.mailbox += [_mail(1, KHAN, ME), _mail(2, ME, KHAN, ("SENT",)), _mail(3, MILLER, ME)]
        conv = h.conversation(surface)

        asked = await conv.say("Send an email to Stephanie on Gmail", _guessing_model)
        assert asked.text == "I found two Stephanies: Stephanie Khan and Stephanie Miller. Which one?"
        assert "to" not in _args(asked), "an ambiguous recipient was chosen silently"
        assert (asked.pending_task or {}).get("status") == "awaiting_params"

        chosen = await conv.say(pick, "Okay.")
        assert _args(chosen)["to"] == "stephanie.khan@acme.example"
        assert "subject" not in _args(chosen), "the choice was also used as the subject"
        assert chosen.text == "Got it, Stephanie Khan. What would you like to say?"
        assert not [c for c in chosen.connector_calls if c.action not in READS]


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_no_stephanie_asks_and_keeps_the_email(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        h.connectors.mailbox.append(_mail(1, "Pat Lee <pat@acme.example>", ME))
        conv = h.conversation(surface)

        missing = await conv.say("Send an email to Stephanie on Gmail", _guessing_model)
        assert missing.text.startswith("I couldn't find Stephanie in this mailbox.")
        assert "to" not in _args(missing), "an invented address survived a failed lookup"
        assert (missing.pending_task or {}).get("status") == "awaiting_params"

        given = await conv.say("It's stephanie@acme.example", "Okay.")
        assert _args(given)["to"] == "stephanie@acme.example"


# --- the resolution contract, without the conversation ---------------------


def _msg(frm: str, to: str, labels: tuple[str, ...] = ("INBOX",), cc: str = "") -> dict[str, Any]:
    headers = [{"name": "From", "value": frm}, {"name": "To", "value": to}]
    if cc:
        headers.append({"name": "Cc", "value": cc})
    return {"labelIds": list(labels), "payload": {"headers": headers}}


def test_the_users_own_address_is_never_a_candidate() -> None:
    own = "Stephanie Owner <me@gravitre.example>"
    cands = candidates_from_messages("Stephanie", [_msg(own, KHAN, ("SENT",))])
    assert [c.address for c in cands] == ["stephanie.khan@acme.example"]


def test_a_draft_is_weaker_evidence_and_never_counts_as_sent() -> None:
    cands = candidates_from_messages(
        "Stephanie",
        [_msg(ME, "Stephanie Draft <s.draft@acme.example>", ("DRAFT",)), _msg(KHAN, ME)],
    )
    assert [c.address for c in cands] == ["stephanie.khan@acme.example", "s.draft@acme.example"]
    draft = cands[1]
    assert draft.evidence["draft"] == 1 and draft.evidence["sent"] == 0


def test_one_person_with_two_addresses_is_told_apart_by_domain() -> None:
    cands = candidates_from_messages(
        "Stephanie", [_msg(KHAN, ME), _msg("Stephanie Khan <steph@gmail.example>", ME)]
    )
    question = resolution_question(resolution_from_candidates("Stephanie", cands))
    assert question == (
        "I found two Stephanies: Stephanie Khan at acme.example and Stephanie Khan at gmail.example. Which one?"
    )
    assert pick_candidate("the gmail one", cands).address == "steph@gmail.example"


def test_cc_and_address_aliases_count_and_lists_do_not_match_a_person() -> None:
    cands = candidates_from_messages(
        "Stephanie",
        [_msg(ME, "Sales Team <sales@acme.example>", ("SENT",), cc="<stephanie.k@acme.example>")],
    )
    assert [c.address for c in cands] == ["stephanie.k@acme.example"]


@pytest.mark.parametrize(
    ("message", "bare_ok", "expected"),
    [
        ("Send an email to Stephanie", False, "Stephanie"),
        ("Can you send an email to Stephanie on Gmail?", False, "Stephanie"),
        ("Email Stephanie Khan about the proposal", False, "Stephanie Khan"),
        ("Send it to stephanie@acme.example", False, None),
        ("Stephanie Khan.", True, "Stephanie Khan"),
        ("Thanks!", True, None),
        ("Sorry.", True, None),
        ("Send an email to the team", False, None),
    ],
)
def test_extract_recipient_name(message: str, bare_ok: bool, expected: str | None) -> None:
    assert extract_recipient_name(message, bare_ok=bare_ok) == expected


def test_a_pick_that_fits_two_candidates_picks_nobody() -> None:
    cands = [
        RecipientCandidate(name="Stephanie Khan", address="sk@acme.example", source="gmail"),
        RecipientCandidate(name="Stephanie Miller", address="sm@acme.example", source="gmail"),
    ]
    assert pick_candidate("Stephanie", cands) is None
    assert pick_candidate("acme", cands) is None
    assert pick_candidate("Miller", cands).address == "sm@acme.example"
