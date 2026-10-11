"""A full email conversation, replayed on both surfaces.

Mirrors the live voice test from 2026-10-11: the email starts without its
details, the user answers with fragments ("Gmail.", "No.", "Sorry."), asks
whether it was sent, fills the subject and the message one at a time, holds
the approval ("Yes... wait."), approves naturally ("Okay, go ahead."), then
asks again and says "Try again." after the send. The send must happen exactly
once, nothing may trigger a web search, and every reply must read like a
person rather than a form.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from tests.scenarios.conversation_harness import BrainCall, Reply, ScenarioHarness, TurnResult

SURFACES = ("text", "voice")
RECIPIENT = "stephanie@acme.example"


def _start_send(call: BrainCall) -> Reply:
    if call.after_tool:
        return Reply(text="Done.")
    name = next((t for t in call.tool_names if "gmail" in t and "send" in t), None)
    if not name:
        return Reply(text="What should the email say?")
    return Reply(tool_calls=[(name, {"to": RECIPIENT})])


def _sends(turn: TurnResult) -> list[Any]:
    return [c for c in turn.connector_calls if c.action == "gmail.messages.send"]


def _status(turn: TurnResult) -> str:
    return str((turn.pending_task or {}).get("status") or "")


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_email_conversation_end_to_end(surface: str) -> None:
    searches: list[Any] = []

    async def _fake_search(*args: Any, **kwargs: Any) -> dict[str, Any]:
        searches.append((args, kwargs))
        return {"results": []}

    with ScenarioHarness() as h, patch("app.services.web_research.search_web", _fake_search):
        h.connected.append("gmail")
        conv = h.conversation(surface)

        start = await conv.say("Can you send an email to Stephanie on Gmail?", _start_send)
        assert _status(start) == "awaiting_params"
        assert not _sends(start)

        provider = await conv.say("Gmail.", _start_send)
        assert provider.text.startswith("Got it, Gmail."), provider.text
        assert "subject and message" in provider.text

        no = await conv.say("No.", "Okay.")
        assert "drop the email, or change something" in no.text
        assert _status(no) == "awaiting_params", "a bare no mid-collection dropped the draft"

        retry = await conv.say("Try again... the email now?", _start_send)
        assert retry.text.startswith("I can't send it yet."), retry.text
        assert not _sends(retry)

        sorry = await conv.say("Sorry.", "No problem.")
        assert "still got the email" in sorry.text
        assert _status(sorry) == "awaiting_params"

        status = await conv.say("Did you send the email?", "Not yet.")
        assert status.text.startswith("Not yet."), status.text

        subject = await conv.say("The subject is Quick update.", "Okay.")
        assert subject.text == "What should the email say?", subject.text
        args = ((subject.pending_task or {}).get("params") or {}).get("args") or {}
        assert not str(args.get("body") or "").strip(), "the subject answer was also used as the message"

        body = await conv.say("Tell her the proposal is ready for review.", "Okay.")
        assert _status(body) == "awaiting_confirm"
        assert f"Here's the email to {RECIPIENT}" in body.text
        assert "The proposal is ready for review." in body.text
        assert "Should I send it?" in body.text
        assert "Tell her" not in body.text

        hold = await conv.say("Yes... wait.", "Okay.")
        assert _status(hold) == "awaiting_confirm"
        assert not _sends(hold)

        approve = await conv.say("Okay, go ahead.", "Okay.")
        assert len(_sends(approve)) == 1, "a natural approval did not send exactly once"
        assert RECIPIENT in approve.text
        assert "Verifiedly" not in approve.text and "Suggest only" not in approve.text
        if surface == "voice":
            assert "View in" not in approve.text, "link labels were spoken"
        else:
            assert "\n\n" in approve.text, "paragraph breaks were collapsed"

        after = await conv.say("Did you send the email?", "Okay.")
        assert after.text.startswith("Yes, it went to"), after.text
        assert not _sends(after)

        again = await conv.say("Try again.", "Okay.")
        assert not _sends(again), "a bare retry after a confirmed send sent a duplicate"
        assert "won't send a duplicate" in again.text

    assert not searches, f"the email conversation triggered {len(searches)} web searches"
