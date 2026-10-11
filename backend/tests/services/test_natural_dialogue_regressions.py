"""Live email repair: shared chat/voice dialogue without implied execution."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from app.services.action_lifecycle import recent_write_status_turn
from app.services.adaptive_research_cascade import should_run_internet_research
from app.services.conversation_tier import classify_conversation_tier, is_social_repair
from app.services.intent_gateway import GatewayContext, evaluate_intent_gateway
from app.services.pipecat_voice.voice_silence_guard import pick_deep_acknowledgement
from app.services.pipecat_voice.voice_tool_narration import skip_spoken_tool_progress


def _draft(status="awaiting_details"):
    return {
        "pending_task": {
            "type": "connector_action",
            "status": status,
            "params": {
                "integration": "gmail",
                "invoke_action": "gmail.messages.send",
                "kind": "write",
                "args": {"to": "stephanie@test.example"},
            },
        }
    }


@pytest.mark.parametrize(
    "message",
    [
        "the workplace or the dog. Try again. Can you try it on the email now?",
        "Try the email again.",
        "Send the email to Stephanie on Gmail.",
        "Change the email to Stephanie instead.",
    ],
)
def test_email_revisions_reach_existing_task_handler(message):
    # Applies even when a preceding task exists: mentioning an email is not
    # asking whether an old provider write completed.
    for state in ({}, _draft()):
        assert recent_write_status_turn(message, state) is None


@pytest.mark.parametrize(
    "message", ["What's the email subject?", "Which contact should I use?"]
)
def test_identity_question_without_prior_result_stays_with_current_draft(message):
    assert recent_write_status_turn(message, _draft()) is None


@pytest.mark.parametrize(
    "message",
    [
        "Did you understand me?",
        "Did that make sense?",
        "Did you have a good day?",
        "Did you remember my name?",
        "Did you finish your coffee?",
        "Did you run a 5k?",
    ],
)
def test_conversational_questions_are_not_intercepted_as_action_status(message):
    for state in ({}, _draft()):
        assert recent_write_status_turn(message, state) is None


@pytest.mark.parametrize(
    "message", ["Sorry.", "I'm sorry.", "My bad.", "Sorry about that."]
)
@pytest.mark.parametrize("spoken", [False, True])
@pytest.mark.parametrize("status", ["awaiting_details", "awaiting_confirm"])
async def test_apology_acknowledges_without_consuming_or_cancelling_draft(
    message, spoken, status
):
    state = _draft(status)
    original = deepcopy(state)
    decision = await evaluate_intent_gateway(
        GatewayContext(
            message=message,
            spoken_mode=spoken,
            task_state=state,
            conversation_history=[
                {"role": "user", "content": "Send an email to Stephanie on Gmail."},
                {"role": "assistant", "content": "What should it say?"},
            ],
        )
    )
    assert decision.action == "shortcut"
    assert decision.answer == "No problem."
    assert decision.extras["provider_invoked"] is False
    assert state == original
    assert pick_deep_acknowledgement(message=message) == ""


@pytest.mark.parametrize(
    "message",
    [
        "Sorry, send it now.",
        "Sorry, use Outlook instead.",
        "Sorry, yes… wait.",
        "My bad, cancel it.",
        "Sorry, research the latest AI news.",
    ],
)
def test_apology_prefix_never_hides_real_request(message):
    assert not is_social_repair(message)
    assert classify_conversation_tier(message).tier != "light"


def test_pure_apology_does_not_inherit_previous_business_depth():
    tier = classify_conversation_tier(
        "Sorry.",
        history=[
            {"role": "user", "content": "Send an email to Stephanie on Gmail."},
            {"role": "assistant", "content": "What should the email say?"},
        ],
    )
    assert tier.tier == "light"


def test_apology_cannot_become_public_research_even_when_internal_context_is_thin(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.adaptive_research_cascade._internet_research_allowed",
        lambda _: True,
    )
    assert not should_run_internet_research(
        "internet_research",
        settings=SimpleNamespace(),
        internal_thin=True,
        query="Sorry.",
    )
    assert should_run_internet_research(
        "internet_research",
        settings=SimpleNamespace(),
        internal_thin=True,
        query="Sorry, research the latest AI news.",
    )


@pytest.mark.parametrize("spoken", [False, True])
@pytest.mark.parametrize(
    "message",
    [
        "How is your day? Mine has been a little hectic.",
        "How are you? My day has been hectic.",
    ],
)
async def test_open_ended_small_talk_uses_existing_reasoning_instead_of_generic_greeting(
    spoken, message
):
    decision = await evaluate_intent_gateway(
        GatewayContext(
            message=message,
            spoken_mode=spoken,
        )
    )
    assert decision.action == "fallthrough"
    assert decision.answer is None


async def test_repeated_canned_opener_falls_through_to_contextual_reply():
    first = await evaluate_intent_gateway(GatewayContext(message="hello there"))
    second = await evaluate_intent_gateway(
        GatewayContext(
            message="hello there",
            conversation_history=[{"role": "assistant", "content": first.answer}],
        )
    )
    assert first.action == "shortcut"
    assert second.action == "fallthrough"


@pytest.mark.parametrize(
    "status", ["awaiting_confirm", "failed", "outcome_uncertain", "executing"]
)
def test_status_uses_plain_language_without_saying_email_was_created(status):
    result = recent_write_status_turn("Did you send it?", _draft(status))
    assert result is not None
    assert result["provider_write"] is False
    assert "contact" not in result["message"].lower()
    assert "created" not in result["message"].lower()
    assert "prior write" not in result["message"].lower()
    assert not result["message"].lower().startswith("yes")


def test_unknown_status_does_not_invent_success_or_failure():
    result = recent_write_status_turn("Did you send it?", {})
    assert (
        result["message"]
        == "I can't confirm that it went through from what I have here."
    )
    assert result["provider_write"] is False


def test_knowledge_bookkeeping_is_silent_but_business_tool_progress_remains():
    assert skip_spoken_tool_progress("searchKnowledgeBase")
    assert skip_spoken_tool_progress("search_knowledge_base")
    assert not skip_spoken_tool_progress("searchDeals")
    assert not skip_spoken_tool_progress("sendEmail")
