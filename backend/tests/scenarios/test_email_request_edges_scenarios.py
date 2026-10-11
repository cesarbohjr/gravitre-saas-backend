"""Email requests at the edges: drafts, pleasantries, and asking once.

Each case was found replaying chat and voice turns on 2026-10-11:

* "Draft an email to ..." answered "That tool isn't connected yet." with
  Gmail connected (Gmail drafts are not a governed write yet).
* "Thanks!" while the email still had no recipient became its subject.
* On voice, the model's spoken question was followed by a second, formal
  one ("I need a few more details to send the email: what to, subject and
  message should I use?").
"""
from __future__ import annotations

import pytest

from tests.scenarios.conversation_harness import BrainCall, Reply, ScenarioHarness

SURFACES = ("text", "voice")


def _asks(call: BrainCall) -> Reply:
    if call.after_tool:
        return Reply(text="Done.")
    return Reply(text="Who should it go to, and what should it say?")


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize(
    "message",
    [
        "Draft an email to pat@acme.example saying hello.",
        "Can you draft an email to Pat about the proposal?",
    ],
)
async def test_a_draft_request_gets_an_honest_answer(surface: str, message: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        turn = await h.conversation(surface).say(message, _asks)
        assert "isn't connected" not in turn.text
        assert "can't save drafts in Gmail yet" in turn.text
        assert not turn.connector_calls
        assert not turn.pending_task


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_an_email_about_a_draft_is_still_a_send(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        turn = await h.conversation(surface).say(
            "Send an email about the draft proposal to pat@acme.example", _asks
        )
        assert "can't save drafts" not in turn.text
        assert (turn.pending_task or {}).get("status") == "awaiting_params"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_thanks_is_not_the_subject_and_the_question_is_asked_once(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        conv = h.conversation(surface)
        first = await conv.say("Can you send an email to Stephanie on Gmail?", _asks)
        assert (first.pending_task or {}).get("status") == "awaiting_params"
        assert first.text.count("?") == 1, first.text
        assert "should I use" not in first.text

        thanks = await conv.say("Thanks!", "You're welcome.")
        args = ((thanks.pending_task or {}).get("params") or {}).get("args") or {}
        assert "Thanks" not in str(args.get("subject") or "")
        assert "Thanks" not in str(args.get("body") or "")
        assert not thanks.connector_calls


@pytest.mark.parametrize(
    ("missing", "args", "expected"),
    [
        (["to", "subject", "body"], {}, "Who should the email go to, and what should the subject and message be?"),
        (["body"], {}, "What should the email say?"),
        (["to", "body"], {}, "Who should the email go to, and what should it say?"),
        (["subject", "body"], {}, "What should the subject and message be for the email?"),
    ],
)
def test_missing_details_question_reads_like_a_person(missing, args, expected) -> None:
    from app.services.action_workflow_validation import missing_details_question

    assert missing_details_question("Send email", missing, args) == expected
