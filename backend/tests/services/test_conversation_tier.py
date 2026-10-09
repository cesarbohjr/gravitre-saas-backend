"""Conversation tier classifier: light / medium / deep, history- and state-aware.

Synthetic utterances; no network, no DB.
"""
from __future__ import annotations

import pytest

from app.services.conversation_tier import (
    classify_conversation_tier,
    has_pending_task_state,
    is_continuation_utterance,
    tier_to_execution_mode,
)
from app.services.operator_task_intent import (
    resolve_default_text_intelligence_mode,
    resolve_voice_session_intelligence_mode,
    resolve_voice_turn_routing,
    use_spoken_lite_path,
)
from tests.services.task_execution_parity_fixtures import (
    AMBIGUOUS_CLARIFY,
    CONNECTOR_LOOKUP,
    GOOGLE_ADS_CAMPAIGN_BRIEF,
    MULTI_PARAM_WRITE,
    SEO_PLUS_GOOGLE_ADS,
    VENTING_PLUS_GOOGLE_ADS,
)

DEEP_EXCHANGE = [
    {"role": "user", "content": "pull my pipeline from HubSpot"},
    {
        "role": "assistant",
        "content": "You have 12 open deals worth about 340k. Want me to draft follow-ups for the stalled ones?",
    },
]
OFFERED_LIST = [
    {"role": "user", "content": "which leads in Apollo should I prioritise this week?"},
    {
        "role": "assistant",
        "content": "Here are three options: Acme, Globex, or Initech. Which one should I enrich first?",
    },
]
JOKE_EXCHANGE = [
    {"role": "user", "content": "tell me a joke"},
    {
        "role": "assistant",
        "content": "Why did the scarecrow win an award? He was outstanding in his field. Want another?",
    },
]
DOG_NAMES = [
    {"role": "user", "content": "give me three names for my dog"},
    {"role": "assistant", "content": "Biscuit, Juniper, or Moose. Which one do you like?"},
]
PENDING_APPROVAL = {
    "pending_action": {"id": "pa-1", "status": "awaiting_user", "params": {"invoke_action": "hubspot.update_deal"}}
}
OFFERED_ACTION = {
    "offered_action": {
        "id": "oa-1",
        "type": "business_health_check",
        "scope": ["connectors"],
        "tools": ["connector_status"],
        "status": "awaiting_user_confirmation",
    }
}
OPTION_SET = {"previous_option_set": [{"id": "a", "label": "Acme"}, {"id": "b", "label": "Globex"}]}

# (message, history, task_state, expected tier)
TABLE: list[tuple[str, list | None, dict | None, str]] = [
    # light: social / phatic, no business noun, no task verb
    ("Hello!", None, None, "light"),
    ("hey, how was your weekend?", None, None, "light"),
    ("haha that's funny", None, None, "light"),
    ("haha nice", None, None, "light"),
    ("tell me a joke", None, None, "light"),
    ("thanks so much", None, None, "light"),
    ("bye!", None, None, "light"),
    ("good morning! how are you?", None, None, "light"),
    ("I'm so tired today", None, None, "light"),
    ("that's wild", None, None, "light"),
    ("did you watch the game last night?", None, None, "light"),
    ("nice weather today", None, None, "light"),
    ("can you hear me?", None, None, "light"),
    ("what's up", None, None, "light"),
    ("who are you?", None, None, "light"),
    # medium: explanations, definitions, opinions, brainstorming
    ("what does merge mean in git?", None, None, "medium"),
    ("what does deploy mean", None, None, "medium"),
    ("what's a CI pipeline?", None, None, "medium"),
    ("what is HubSpot?", None, None, "medium"),
    ("explain the difference between TCP and UDP", None, None, "medium"),
    ("compare python and go for a small backend", None, None, "medium"),
    ("give me ideas for a team offsite", None, None, "medium"),
    ("how do I get more leads?", None, None, "medium"),
    ("write me a poem about the sea", None, None, "medium"),
    ("", None, None, "medium"),
    ("   ", None, None, "medium"),
    # deep: operator tasks, connectors, business data, operational verbs, research
    ("How many companies are in my HubSpot?", None, None, "deep"),
    ("how many companies in HubSpot", None, None, "deep"),
    ("hey can you pull my pipeline", None, None, "deep"),
    ("Investigate my production logs", None, None, "deep"),
    ("Create four campaigns in Google Ads", None, None, "deep"),
    ("what's our revenue this quarter", None, None, "deep"),
    ("merge the PR", None, None, "deep"),
    ("deploy to staging", None, None, "deep"),
    ("research the latest trends in AI agents", None, None, "deep"),
    ("run the weekly report", None, None, "deep"),
    ("send an email to Sarah", None, None, "deep"),
    ("create an agent that triages support tickets", None, None, "deep"),
    ("haha ok, can you check my Gmail", None, None, "deep"),
    (GOOGLE_ADS_CAMPAIGN_BRIEF, None, None, "deep"),
    (CONNECTOR_LOOKUP, None, None, "deep"),
    (MULTI_PARAM_WRITE, None, None, "deep"),
    (SEO_PLUS_GOOGLE_ADS, None, None, "deep"),
    (VENTING_PLUS_GOOGLE_ADS, None, None, "deep"),
    # continuations inherit the exchange they answer
    ("yes, do that", DEEP_EXCHANGE, None, "deep"),
    ("sure", DEEP_EXCHANGE, None, "deep"),
    ("ok send it", DEEP_EXCHANGE, None, "deep"),
    # backing off after deep work is answered at once, never deep
    ("no wait", DEEP_EXCHANGE, None, "light"),
    ("cancel that", DEEP_EXCHANGE, None, "light"),
    ("the second one", OFFERED_LIST, None, "deep"),
    ("the second one", None, OPTION_SET, "deep"),
    ("yes", None, PENDING_APPROVAL, "deep"),
    ("go ahead", None, OFFERED_ACTION, "deep"),
    ("yes", [{"role": "assistant", "content": "Want me to check that?"}], None, "deep"),
    ("sure", JOKE_EXCHANGE, None, "light"),
    ("the second one", DOG_NAMES, None, "light"),
    ("yes, do that", None, None, "medium"),
    # mid-task small talk is never light
    ("haha nice", None, PENDING_APPROVAL, "medium"),
    ("thanks!", None, OFFERED_ACTION, "medium"),
]


@pytest.mark.parametrize(("message", "history", "task_state", "expected"), TABLE)
def test_tier_table(message, history, task_state, expected) -> None:
    result = classify_conversation_tier(message, history=history, task_state=task_state)
    assert result.tier == expected, (message, result)
    assert result.reason


def test_table_is_large_enough() -> None:
    assert len(TABLE) >= 40


def test_reaction_after_deep_answer_is_still_light_without_pending_state() -> None:
    # A reaction is not a continuation; nothing is pending, so no work is lost.
    assert classify_conversation_tier("haha nice", history=DEEP_EXCHANGE).tier == "light"


def test_classifier_is_deterministic() -> None:
    for message, history, task_state, _ in TABLE:
        a = classify_conversation_tier(message, history=history, task_state=task_state)
        b = classify_conversation_tier(message, history=history, task_state=task_state)
        assert a == b


def test_history_holding_current_utterance_is_tolerated() -> None:
    history = [*DEEP_EXCHANGE, {"role": "user", "content": "yes, do that"}]
    assert classify_conversation_tier("yes, do that", history=history).tier == "deep"


def test_continuation_and_pending_helpers() -> None:
    for text in ("yes, do that", "the second one", "ok send it", "no wait", "go ahead", "cancel that", "sure"):
        assert is_continuation_utterance(text), text
    for text in ("tell me a joke", "how many deals do we have", ""):
        assert not is_continuation_utterance(text), text
    assert has_pending_task_state(PENDING_APPROVAL)
    assert has_pending_task_state(OFFERED_ACTION)
    assert has_pending_task_state({"execution_plan": {"plan_id": "p", "terminal_status": "waiting_for_approval"}})
    assert not has_pending_task_state({"execution_plan": {"plan_id": "p", "terminal_status": "completed"}})
    assert not has_pending_task_state({})
    assert not has_pending_task_state(None)


def test_tier_to_mode() -> None:
    assert tier_to_execution_mode("light") == "fast"
    assert tier_to_execution_mode("medium") == "standard"
    assert tier_to_execution_mode("deep") == "agent"


# --- lite path -----------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "How many companies are in my HubSpot?",
        "hey can you pull my pipeline",
        "what's our revenue this quarter",
        "Is Apollo connected?",
        "send an email to Sarah",
        GOOGLE_ADS_CAMPAIGN_BRIEF,
        CONNECTOR_LOOKUP,
        MULTI_PARAM_WRITE,
        "what does merge mean in git?",
        AMBIGUOUS_CLARIFY,
    ],
)
def test_lite_path_never_taken_for_business_or_non_light(message: str) -> None:
    assert not use_spoken_lite_path(spoken_mode=True, routing_tier="simple", message=message)


@pytest.mark.parametrize("message", ["haha nice", "thanks!", "hey, how was your weekend?", "yes"])
def test_lite_path_never_taken_with_pending_state(message: str) -> None:
    for state in (PENDING_APPROVAL, OFFERED_ACTION):
        assert not use_spoken_lite_path(
            spoken_mode=True, routing_tier="simple", message=message, task_state=state
        )


def test_lite_path_not_taken_for_continuation_of_deep_exchange() -> None:
    assert not use_spoken_lite_path(
        spoken_mode=True, routing_tier="simple", message="yes, do that", history=DEEP_EXCHANGE
    )


@pytest.mark.parametrize(
    "message", ["hey, how was your weekend?", "haha that's funny", "tell me a joke", "thanks so much"]
)
def test_lite_path_taken_for_small_talk(message: str) -> None:
    assert use_spoken_lite_path(spoken_mode=True, routing_tier="simple", message=message)
    # Typed turns and escalated routing never take it.
    assert not use_spoken_lite_path(spoken_mode=False, routing_tier="simple", message=message)
    assert not use_spoken_lite_path(spoken_mode=True, routing_tier="multi_step", message=message)


# --- modes -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # Previously tested text-path expectations, unchanged.
        (GOOGLE_ADS_CAMPAIGN_BRIEF, "agent"),
        (CONNECTOR_LOOKUP, "agent"),
        ("hey, how's it going", "fast"),
        # Text keeps the operator-task rule even where the voice tier is deep.
        ("How many companies are in my HubSpot?", "fast"),
        ("what's our revenue this quarter", "fast"),
    ],
)
def test_text_default_mode_is_backward_compatible(message: str, expected: str) -> None:
    assert resolve_default_text_intelligence_mode(message) == expected


def test_voice_mode_follows_tier_and_history() -> None:
    assert resolve_voice_session_intelligence_mode("Hello!") == "fast"
    assert resolve_voice_session_intelligence_mode("explain TCP vs UDP") == "standard"
    assert resolve_voice_session_intelligence_mode("How many companies are in my HubSpot?") == "agent"
    assert resolve_voice_session_intelligence_mode("yes, do that") == "standard"
    assert resolve_voice_session_intelligence_mode("yes, do that", history=DEEP_EXCHANGE) == "agent"
    tier, mode = resolve_voice_turn_routing("yes, do that", history=DEEP_EXCHANGE)
    assert (tier.tier, mode) == ("deep", "agent")


# --- trace -----------------------------------------------------------------------


def test_tier_is_carried_on_the_loop_trace_and_latency_audit() -> None:
    from app.services.cognitive_loop_controller import CognitiveLoopTrace
    from app.services.turn_latency_trace import record_critical_path

    trace = CognitiveLoopTrace(loop_id="l1", message="hi", spoken_mode=True, operator_task=False)
    tier = classify_conversation_tier("hey, how was your weekend?")
    trace.conversation_tier, trace.conversation_tier_reason = tier.tier, tier.reason
    assert trace.to_sse()["conversationTier"] == "light"
    assert trace.to_sse()["conversationTierReason"] == "social"
    assert trace.to_dict()["conversation_tier"] == "light"
    # No org/user: analysis only, nothing written.
    analysis = record_critical_path(
        None, org_id="", user_id=None, conversation_id=None, turn_id="t1", marks={"a": 5}, conversation_tier="light"
    )
    assert analysis["conversation_tier"] == "light"


def test_deep_tier_upgrades_a_pinned_fast_voice_mode() -> None:
    from app.services.conversation_tier import upgrade_spoken_mode_for_tier

    assert upgrade_spoken_mode_for_tier("fast", "deep", spoken_mode=True) == "agent"
    assert upgrade_spoken_mode_for_tier("fast", "medium", spoken_mode=True) == "standard"
    assert upgrade_spoken_mode_for_tier("standard", "deep", spoken_mode=True) == "agent"
    assert upgrade_spoken_mode_for_tier("fast", "light", spoken_mode=True) == "fast"
    assert upgrade_spoken_mode_for_tier("fast", "deep", spoken_mode=False) == "fast"
    assert upgrade_spoken_mode_for_tier("agent", "light", spoken_mode=True) == "agent"
    assert upgrade_spoken_mode_for_tier(None, "deep", spoken_mode=True) is None


def test_pending_approval_confirmation_is_deep_even_without_history() -> None:
    from app.services.conversation_tier import upgrade_spoken_mode_for_tier

    # Voice entry saw no history, so it pinned fast; the brain sees the approval.
    tier = classify_conversation_tier("yes, do that", history=[], task_state=PENDING_APPROVAL)
    assert tier.tier == "deep"
    assert upgrade_spoken_mode_for_tier("fast", tier.tier, spoken_mode=True) == "agent"


# --- 2026-10-09 review: action requests, follow-ups, backing off ---------------

DEALS_ANSWER = [
    {"role": "user", "content": "Show me my open deals in HubSpot"},
    {"role": "assistant", "content": "You have 4 open deals worth $52k. The biggest is Acme at $20k."},
]
FOLLOW_UP_OFFER = [
    {"role": "user", "content": "Who hasn't replied to my last email?"},
    {
        "role": "assistant",
        "content": "Three people haven't replied: Sarah, Mike and Dana. Want me to send them a follow-up?",
    },
]
UNANSWERED_EMAIL = [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": "Hey! What can I do for you?"},
    {"role": "user", "content": "Email Sarah the deck from yesterday"},
]

# Requests that used to route medium/light (fast mode, lite path) and never ran tools.
ACTION_REQUESTS = [
    "Can you text John that I'm running late",
    "Tell Sarah I'll be late",
    "Write a follow up to Acme",
    "Can you write an email to Mike",
    "Thanks, can you also email John the deck?",
    "Got it, thanks. Send it.",
    "Perfect, send it to all of them",
    "Cancel my 3pm",
    "Move my 3pm to 4pm",
    "Could you put a meeting on Friday with Sarah",
    "What meetings do I have tomorrow?",
    "What did I miss today?",
    "What's the status on the Acme deal?",
    "Shoot Sarah an email with the deck",
    "Okay, now do the same for Acme",
    "Yes, and also add Mike",
    "Text Maria happy birthday",
    "Message the team that lunch is on me",
    "Plan my week",
    "Great, now pull up my pipeline",
]


@pytest.mark.parametrize("message", ACTION_REQUESTS)
def test_action_requests_route_deep(message: str) -> None:
    result = classify_conversation_tier(message)
    assert result.tier == "deep", (message, result)


# (message, history, expected tier)
FOLLOW_UP_TABLE: list[tuple[str, list, str]] = [
    ("cool, mark it won", DEALS_ANSWER, "deep"),
    ("Nice, which one closes first?", DEALS_ANSWER, "deep"),
    ("Nice, let's do the second one", DEALS_ANSWER, "deep"),
    ("Same for last month", DEALS_ANSWER, "deep"),
    ("what about last month", DEALS_ANSWER, "deep"),
    ("ok what about Acme", DEALS_ANSWER, "deep"),
    ("and the smallest?", DEALS_ANSWER, "deep"),
    ("great, update it to closed won", DEALS_ANSWER, "deep"),
    ("Thanks", DEALS_ANSWER, "light"),
    ("haha nice", DEALS_ANSWER, "light"),
    ("Sounds great", FOLLOW_UP_OFFER, "deep"),
    ("Yes please, that would be great", FOLLOW_UP_OFFER, "deep"),
    ("Yes and cc me", FOLLOW_UP_OFFER, "deep"),
    ("Sure, but leave Dana out", FOLLOW_UP_OFFER, "deep"),
    ("great", FOLLOW_UP_OFFER, "deep"),
    ("Perfect", FOLLOW_UP_OFFER, "deep"),
    ("and cc Mike", UNANSWERED_EMAIL, "deep"),
    ("actually make it Thursday", UNANSWERED_EMAIL, "deep"),
    ("oh and attach the pricing sheet", UNANSWERED_EMAIL, "deep"),
    # a self-contained new question after deep work is not dragged deep
    ("explain how vector databases work", DEALS_ANSWER, "medium"),
    ("what is the capital of France", DEALS_ANSWER, "medium"),
    ("sure", JOKE_EXCHANGE, "light"),
]


@pytest.mark.parametrize(("message", "history", "expected"), FOLLOW_UP_TABLE)
def test_follow_ups_keep_the_depth_of_the_exchange(message, history, expected) -> None:
    result = classify_conversation_tier(message, history=history)
    assert result.tier == expected, (message, result)


@pytest.mark.parametrize(
    "message",
    ["Same for Facebook", "Nice, which one closes first?", "great, update it to closed won", "Order the report"],
)
def test_light_requires_every_clause_to_be_social(message: str) -> None:
    assert classify_conversation_tier(message).tier != "light"


@pytest.mark.parametrize(
    "message", ["never mind", "no thanks", "nope", "stop", "wait", "hold on", "forget it", "no, thank you"]
)
def test_backing_off_is_never_deep_or_acknowledged(message: str) -> None:
    from app.services.conversation_tier import should_acknowledge_turn

    for state in (None, PENDING_APPROVAL):
        tier = classify_conversation_tier(message, history=DEEP_EXCHANGE, task_state=state)
        assert tier.tier != "deep", (message, state, tier)
        assert not should_acknowledge_turn(tier), (message, state, tier)
    # Pending state keeps a decline off the lite path so the approval sees it.
    assert not use_spoken_lite_path(
        spoken_mode=True, routing_tier="simple", message=message, task_state=PENDING_APPROVAL
    )


@pytest.mark.parametrize(
    "message",
    ["write me a poem about the sea", "tell me a joke", "give me three names for my dog", "give me ideas for a team offsite"],
)
def test_creative_and_self_directed_asks_are_not_tool_work(message: str) -> None:
    assert classify_conversation_tier(message).tier != "deep"


def test_acknowledgement_policy() -> None:
    from app.services.conversation_tier import ConversationTier, should_acknowledge_turn

    assert should_acknowledge_turn(ConversationTier("deep", "operator_task"))
    assert should_acknowledge_turn(ConversationTier("medium", "general"))
    assert not should_acknowledge_turn(ConversationTier("light", "social"))
    assert not should_acknowledge_turn(ConversationTier("medium", "continuation_decline_pending"))
    assert not should_acknowledge_turn(None)
