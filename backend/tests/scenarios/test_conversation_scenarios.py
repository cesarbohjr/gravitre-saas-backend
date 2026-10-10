"""Multi-turn conversation scenarios over the real shared turn path.

Each scenario runs through the text entry (``POST /api/assistant/chat``) and
the voice entry (``GravitreCognitiveLLMService``), with the model and the
connectors faked deterministically (see ``conversation_harness``). The
assertions are on behaviour a person would notice: which data was read and
for which period, whether something was executed or held for approval,
whether a reply is a single question, and whether small talk stayed small.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.services.canonical_time_resolver import (
    previous_comparable_window,
    resolve_time_window,
)
from tests.scenarios.conversation_harness import (
    BrainCall,
    Reply,
    ScenarioHarness,
    TurnResult,
)

SURFACES = ("text", "voice")

TRAFFIC = "what's my website traffic"


# -- helpers ---------------------------------------------------------------


def _ga_calls(turn: TurnResult) -> list[Any]:
    return [c for c in turn.connector_calls if "analytics" in c.action.lower() and "search" not in c.action.lower()]


def _gsc_calls(turn: TurnResult) -> list[Any]:
    return [c for c in turn.connector_calls if "searchconsole" in c.action.lower() or "search_console" in c.action.lower()]


def _window(turn_calls: list[Any]) -> set[tuple[str, str]]:
    return {(str(c.params.get("start_date")), str(c.params.get("end_date"))) for c in turn_calls}


def _dims(call: Any) -> list[str]:
    return [str(d.get("name") if isinstance(d, dict) else d) for d in (call.params.get("dimensions") or [])]


def _last_month() -> tuple[str, str]:
    window = resolve_time_window("last month")
    assert window is not None
    return window.start_iso, window.end_iso


def _questions(text: str) -> int:
    return text.count("?")


def _no_tools(turn: TurnResult) -> None:
    assert turn.connector_calls == [], f"{turn.user!r} read connectors: {turn.connector_calls}"
    for call in turn.brain_calls:
        assert not call.after_tool, f"{turn.user!r} ran a tool round"


def _say(text: str) -> Any:
    return lambda call: Reply(text=text)


# -- corrections -----------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_correction_keeps_the_intent_and_changes_only_the_period(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)
        first = await conv.say(TRAFFIC)
        assert _ga_calls(first), "the traffic question read no analytics"
        first_actions = {c.action for c in first.connector_calls}

        corrected = await conv.say("no, last month")

        assert _ga_calls(corrected), f"the correction was not re-run as a traffic read: {corrected.text!r}"
        assert {c.action for c in corrected.connector_calls} == first_actions, "the correction changed the data source"
        assert _window(_ga_calls(corrected)) == {_last_month()}, "the correction did not move the period to last month"
        assert "last 30 days" not in corrected.text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_correction_switches_the_source_and_keeps_the_period(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)
        await conv.say(TRAFFIC)
        await conv.say("no, last month")

        switched = await conv.say("actually make it Search Console")

        assert _gsc_calls(switched), f"Search Console was not read: {switched.text!r}"
        assert not _ga_calls(switched), "the source switch still read Google Analytics"
        assert _window(_gsc_calls(switched)) == {_last_month()}, "the source switch lost the corrected period"


# -- follow-ups with pronouns / ellipsis ------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_which_pages_did_best_follows_up_on_the_traffic_answer(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)
        await conv.say(f"{TRAFFIC} last month")

        pages = await conv.say("which pages did best?")

        page_reads = [c for c in pages.connector_calls if any("page" in d.lower() for d in _dims(c))]
        assert page_reads, f"no page-level read for the follow-up: {pages.text!r}"
        assert _window(page_reads) == {_last_month()}, "the follow-up lost the period being discussed"
        assert "/pricing" in pages.text
        assert "can't answer" not in pages.text.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_and_the_week_before_reads_the_previous_week(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)
        first = await conv.say(f"{TRAFFIC} last week")
        assert _ga_calls(first)
        last_week = resolve_time_window("last week")
        assert last_week is not None
        week_before = previous_comparable_window(last_week)

        before = await conv.say("and the week before?")

        assert _ga_calls(before), f"the elliptical follow-up was not a traffic read: {before.text!r}"
        assert (week_before.start_iso, week_before.end_iso) in _window(_ga_calls(before))


# -- confirmations ----------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("reply", ["yes do that", "sure", "go ahead"])
async def test_accepting_an_offer_runs_what_was_offered(surface: str, reply: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)
        first = await conv.say(f"{TRAFFIC} last month")
        assert "want me to" in first.text.lower(), "the traffic answer made no offer"

        accepted = await conv.say(reply)

        breakdown = [c for c in accepted.connector_calls if _dims(c)]
        assert breakdown, f"{reply!r} did not run the offered breakdown: {accepted.text!r}"
        assert _window(breakdown) == {_last_month()}
        assert "anything urgent" not in accepted.text.lower(), "ran a generic health check instead of the offer"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("reply", ["no thanks", "not now"])
async def test_declining_an_offer_runs_nothing(surface: str, reply: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)
        await conv.say(TRAFFIC)

        declined = await conv.say(reply, _say("No problem."))

        _no_tools(declined)
        assert declined.text, "no reply to the decline"
        assert len(declined.text) <= 120
        assert "what do you want to get done" not in declined.text.lower(), "a decline was answered as a greeting"


# -- changing the subject and returning --------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_changing_the_subject_then_returning_to_the_traffic(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)
        await conv.say(f"{TRAFFIC} last month")

        side = await conv.say(
            "who owns the Acme account?",
            _say("Dana Reyes owns the Acme account."),
        )
        assert side.brain_called, f"the new subject never reached the model: {side.text!r}"
        assert any(name.startswith("hubspot_") for name in side.brain_tool_offers), "CRM tools were not available"
        assert not side.connector_calls or not _ga_calls(side), "the new subject re-read analytics"
        assert "Dana Reyes" in side.text

        back = await conv.say("ok back to the traffic")

        assert _ga_calls(back), f"returning to the traffic did not read analytics: {back.text!r}"
        assert _window(_ga_calls(back)) == {_last_month()}, "returning to the traffic lost the period"


# -- small talk --------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("message", ["hey how's it going", "thanks!"])
async def test_small_talk_gets_a_short_reply_and_touches_nothing(surface: str, message: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)

        turn = await conv.say(message, _say("Doing well, thanks for asking!"))

        _no_tools(turn)
        assert turn.text
        assert len(turn.text) <= 120
        assert _questions(turn.text) <= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_how_is_it_going_is_answered_not_deflected(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)

        turn = await conv.say("hey how's it going", _say("Doing well, thanks for asking!"))

        _no_tools(turn)
        lowered = turn.text.lower()
        assert any(word in lowered for word in ("good", "well", "great")), f"the question was not answered: {turn.text!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_thanks_after_an_answer_stays_small(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)
        await conv.say(TRAFFIC)

        turn = await conv.say("thanks!", _say("Anytime!"))

        _no_tools(turn)
        assert len(turn.text) <= 120


# -- ambiguity ----------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_ambiguous_request_gets_one_clarifying_question(surface: str) -> None:
    question = "Which numbers do you mean: website traffic or your HubSpot pipeline?"
    with ScenarioHarness() as h:
        conv = h.conversation(surface)

        turn = await conv.say("can you pull the numbers?", _say(question))

        assert turn.brain_called, f"the ambiguous request never reached the model: {turn.text!r}"
        assert turn.connector_calls == [], "guessed and read data instead of asking"
        assert _questions(turn.text) == 1, f"expected exactly one question: {turn.text!r}"
        assert turn.text.count("\n- ") < 3, "dumped a list of options"
        assert "can't answer" not in turn.text.lower()


# -- actions --------------------------------------------------------------------


def _create_task(call: BrainCall) -> Reply:
    if call.after_tool:
        return Reply(text="I've drafted that task.")
    name = next((t for t in call.tool_names if "task" in t and "create" in t), None)
    assert name, f"no task-creation tool offered: {call.tool_names}"
    return Reply(
        tool_calls=[
            (
                name,
                {
                    "name": "Follow up with Acme",
                    "notes": "Check in on the renewal.",
                    "project": "1209",
                    "due_on": "2026-10-16",
                },
            )
        ]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_action_request_is_held_for_approval_then_executed_on_yes(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)

        asked = await conv.say("create a follow-up task for Acme", _create_task)

        assert asked.brain_called
        assert asked.connector_calls == [], "a write ran before approval"
        pending = asked.pending_task
        assert pending is not None, f"the write was described, not staged: {asked.text!r}"
        assert "task" in str(pending).lower()

        done = await conv.say("yes")

        writes = [c for c in done.connector_calls if c.action.lower().endswith("tasks.create")]
        assert len(writes) == 1, f"approved write did not run exactly once: {done.connector_calls} / {done.text!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_action_request_from_a_member_is_sent_for_approval_not_run(surface: str) -> None:
    with ScenarioHarness(role="member") as h:
        conv = h.conversation(surface)
        asked = await conv.say("create a follow-up task for Acme", _create_task)
        assert asked.pending_task is not None

        done = await conv.say("yes")

        assert done.connector_calls == [], "a member's write ran without an admin's approval"
        assert "approval" in done.text.lower(), f"the member was not told it went for approval: {done.text!r}"


def _create_task_without_due_date(call: BrainCall) -> Reply:
    reply = _create_task(call)
    if reply.tool_calls:
        name, args = reply.tool_calls[0]
        reply = Reply(tool_calls=[(name, {k: v for k, v in args.items() if k != "due_on"})])
    return reply


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_action_request_missing_a_detail_asks_for_that_detail(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)

        asked = await conv.say("create a follow-up task for Acme", _create_task_without_due_date)

        assert asked.connector_calls == []
        assert _questions(asked.text) == 1, f"expected one question: {asked.text!r}"
        assert "due" in asked.text.lower(), f"the question does not name the missing detail: {asked.text!r}"
        assert "target" not in asked.text.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_action_request_declined_does_not_execute(surface: str) -> None:
    with ScenarioHarness() as h:
        conv = h.conversation(surface)
        asked = await conv.say("create a follow-up task for Acme", _create_task)
        assert asked.pending_task is not None

        declined = await conv.say("no")

        assert declined.connector_calls == []


# -- interruption (voice) -----------------------------------------------------------


@pytest.mark.asyncio
async def test_interrupted_voice_reply_then_new_request_answers_the_new_request() -> None:
    with ScenarioHarness() as h:
        conv = h.conversation("voice")
        await conv.interrupt_before_reply(TRAFFIC)

        turn = await conv.say("who owns the Acme account?", _say("Dana Reyes owns the Acme account."))

        assert turn.brain_called
        asked = turn.brain_calls[0].last_user
        assert "who owns the Acme account?" in asked
        # The turn prompt also lists tool names (some mention traffic), so look
        # for the interrupted request itself, joined to the new one.
        assert TRAFFIC not in asked.lower(), "the interrupted request was merged into the new one"
        assert "traffic, who owns" not in asked.lower()
        assert not _ga_calls(turn), "answered the interrupted traffic request instead"
        assert "Dana Reyes" in turn.text


@pytest.mark.asyncio
async def test_interrupted_voice_request_is_completed_by_a_fragment() -> None:
    with ScenarioHarness() as h:
        conv = h.conversation("voice")
        await conv.interrupt_before_reply(TRAFFIC)

        turn = await conv.say("for last month")

        assert _ga_calls(turn), f"the fragment did not complete the interrupted request: {turn.text!r}"
        assert _window(_ga_calls(turn)) == {_last_month()}


@pytest.mark.asyncio
async def test_reply_cut_off_mid_answer_then_new_request_answers_the_new_request() -> None:
    with ScenarioHarness() as h:
        conv = h.conversation("voice")
        await conv.interrupt_mid_reply(TRAFFIC)

        turn = await conv.say("who owns the Acme account?", _say("Dana Reyes owns the Acme account."))

        assert not _ga_calls(turn)
        assert "Dana Reyes" in turn.text


# -- parity ------------------------------------------------------------------------

PARITY_SCRIPT = [
    (TRAFFIC, None),
    ("no, last month", None),
    ("which pages did best?", None),
    ("thanks!", _say("Anytime!")),
    ("create a follow-up task for Acme", _create_task),
    ("yes", None),
]


def _signature(turn: TurnResult) -> tuple[Any, ...]:
    pending = turn.pending_task or {}
    return (
        turn.model.split(":")[0] if turn.model.startswith("intent_gateway") else bool(turn.brain_called),
        tuple(sorted({c.action for c in turn.connector_calls})),
        tuple(sorted(_window(turn.connector_calls))),
        str(pending.get("status") or ""),
    )


@pytest.mark.asyncio
async def test_text_and_voice_reach_the_same_decisions() -> None:
    signatures: dict[str, list[tuple[Any, ...]]] = {}
    for surface in SURFACES:
        with ScenarioHarness() as h:
            conv = h.conversation(surface)
            signatures[surface] = []
            for message, model in PARITY_SCRIPT:
                turn = await conv.say(message, model)
                signatures[surface].append(_signature(turn))
    for idx, (message, _model) in enumerate(PARITY_SCRIPT):
        assert signatures["text"][idx] == signatures["voice"][idx], (
            f"text and voice diverged on {message!r}: {signatures['text'][idx]} vs {signatures['voice'][idx]}"
        )
