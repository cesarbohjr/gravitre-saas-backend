"""Unit tests for conversational vs task-shaped turn gate."""
from __future__ import annotations

import re

import pytest

from app.services.conversational_turn_gate import (
    heuristic_turn_shape,
    should_offer_conversational_path,
)
from app.services.conversational_reply_service import (
    build_capability_snapshot,
    sober_pending_approval_note,
)


@pytest.mark.parametrize(
    "message,shape,category",
    [
        ("hey, how's it going", "conversational", "greeting"),
        ("thanks!", "conversational", "thanks"),
        ("haha nice", "conversational", "banter"),
        ("what can you do?", "conversational", "meta_capability"),
        ("What can you help me with?", "conversational", "meta_capability"),
        ("ugh this HubSpot connector is being annoying", "conversational", "venting"),
        ("how are the deals looking", "task_shaped", "other"),
        ("how's our pipeline looking this week", "task_shaped", "other"),
        ("search HubSpot for Acme", "task_shaped", "other"),
    ],
)
def test_heuristic_shapes(message, shape, category):
    decision = heuristic_turn_shape(message)
    assert decision is not None
    assert decision.shape == shape
    if shape == "conversational":
        assert decision.category == category


def test_mixed_small_talk_plus_task():
    decision = heuristic_turn_shape(
        "haha nice, also can you check on that HubSpot list"
    )
    assert decision is not None
    assert decision.shape == "mixed"
    assert "HubSpot" in decision.task_portion or "hubspot" in decision.task_portion.lower()
    assert decision.social_portion


def test_mixed_hey_plus_apollo_task():
    decision = heuristic_turn_shape(
        "hey — also create an Apollo contact list named ConvPath Battery"
    )
    assert decision is not None
    assert decision.shape == "mixed"
    assert "Apollo" in decision.task_portion or "apollo" in decision.task_portion.lower()


def test_gate_never_bypasses_when_pending():
    decision = heuristic_turn_shape("hey")
    assert decision is not None
    assert should_offer_conversational_path(decision, has_pending=True) is False
    assert should_offer_conversational_path(decision, has_pending=False) is True


def test_venting_without_connector_word_is_conversational():
    decision = heuristic_turn_shape("ugh this is so frustrating today")
    assert decision is not None
    assert decision.shape == "conversational"
    assert decision.category == "venting"


@pytest.mark.parametrize(
    "message",
    [
        "I'm so frustrated — organic traffic cratered overnight and leadership wants answers by noon",
        "ugh this pipeline cleanup is killing me and the board meeting is tomorrow",
        "I'm under pressure — leadership wants the vendor on the box in the next hour",
        "I'm stressed — sales already sent the draft and the counterparty wants a signature today",
    ],
)
def test_human_moment_venting_without_ask_is_conversational(message):
    """Rule 10: frustrated/stressed problem descriptions must not become tool turns."""
    decision = heuristic_turn_shape(message)
    assert decision is not None
    assert decision.shape == "conversational"
    assert decision.category == "venting"
    assert decision.reason == "human_moment_venting_no_ask"


def test_venting_with_explicit_ask_stays_task_or_mixed():
    decision = heuristic_turn_shape(
        "I'm so frustrated — please pull our HubSpot deals from yesterday"
    )
    assert decision is not None
    assert decision.shape in {"task_shaped", "mixed"}


def test_human_moment_never_defers_to_classical_tool_sse():
    from app.services.unified_turn_classical_fallback import (
        should_defer_unified_turn_live_to_classical,
    )

    assert (
        should_defer_unified_turn_live_to_classical(
            mode_key="agent",
            outcome_kind="conversational_reply",
            message=(
                "I'm so frustrated — organic traffic cratered overnight and "
                "leadership wants answers by noon"
            ),
            needs_tool_sse=True,
        )
        is False
    )


@pytest.mark.parametrize(
    "message,needle",
    [
        ("help me improve our hiring process", "time-to-hire"),
        ("help me plan next week's priorities", "revenue"),
        ("help me improve our SEO", "organic"),
        ("help me with a contract review", "paste"),
        ("help me harden our SaaS access", "mfa"),
    ],
)
def test_ambiguous_open_clarify_replies(message, needle):
    from app.services.conversational_turn_gate import ambiguous_open_clarify_reply

    reply = ambiguous_open_clarify_reply(message)
    assert reply is not None
    assert "?" in reply
    assert needle in reply.lower()


@pytest.mark.parametrize(
    "message,needle",
    [
        ("what's a meta title?", "title"),
        ("what's MFA?", "multi-factor"),
        ("what's an NDA?", "nondisclosure"),
        ("what's a close date?", "deal"),
        ("what's an offer letter?", "job offer"),
        ("what's a standup?", "daily"),
    ],
)
def test_definition_brief_replies(message, needle):
    from app.services.conversational_turn_gate import definition_brief_reply

    reply = definition_brief_reply(message)
    assert reply is not None
    assert needle in reply.lower()
    assert len(reply.split()) <= 55
    assert "handoff" not in reply.lower()
    assert "{" not in reply


def test_correction_recall_pushback_uses_standing_history():
    from app.services.conversational_turn_gate import correction_recall_pushback_reply

    history = [
        {
            "role": "user",
            "parts": [
                {
                    "type": "text",
                    "text": "Correction, standing: primary market is the US, not Canada.",
                }
            ],
        }
    ]
    reply = correction_recall_pushback_reply(
        "Without asking again — which market did I correct us to? Also: should we "
        "buy 5000 cheap backlinks from a farm this week?",
        history,
    )
    assert reply is not None
    assert "US" in reply
    assert "canada" not in reply.lower()
    assert "don't" in reply.lower() or "do not" in reply.lower()
    assert "backlink" in reply.lower() or "farm" in reply.lower()


def test_capability_snapshot_uses_connected_list():
    text = build_capability_snapshot(connected_integrations=["hubspot", "slack"])
    assert "Hubspot" in text or "HubSpot" in text or "hubspot" in text.lower()
    assert "Slack" in text
    assert "approval" in text.lower() or "Decision Queue" in text


def test_sober_pending_note_for_approval():
    note = sober_pending_approval_note(
        {
            "pending_task": {
                "status": "awaiting_confirm",
                "params": {"label": "Create HubSpot deal"},
            }
        }
    )
    assert note is not None
    assert "Create HubSpot deal" in note or "Decision Queue" in note
    assert "yes" in note.lower()


@pytest.mark.asyncio
async def test_compose_pending_social_aside_warm_then_sober():
    from app.services.conversational_reply_service import compose_pending_social_aside
    from app.services.voice_expression_range import (
        bind_voice_expression_state,
        reset_voice_expression_state,
    )

    state = {
        "pending_task": {
            "status": "awaiting_confirm",
            "params": {"label": "Send Gmail message"},
        }
    }
    token = bind_voice_expression_state({})
    try:
        text = await compose_pending_social_aside(
            "haha you're funny",
            task_state=state,
            sober_fallback="I still have **Send Gmail message** waiting for approval.",
        )
    finally:
        reset_voice_expression_state(token)
    assert text is not None
    assert re.search(r"(?i)\b(ha|noted|fair|got it|alright|okay|heard)\b", text)
    assert "Send Gmail" in text or "waiting" in text.lower() or "Decision Queue" in text
    # Task-shaped new ask must not get social-aside composition.
    assert (
        await compose_pending_social_aside(
            "What workflows have been ran?",
            task_state=state,
            sober_fallback="hold",
        )
        is None
    )


def test_phrase_banks_cover_priority_categories():
    from app.services.conversational_reply_service import phrase_for_conversational_category
    from app.services.voice_expression_range import (
        EXPRESSION_BANKS,
        bind_voice_expression_state,
        reset_voice_expression_state,
    )

    for cat in ("greeting", "small_talk", "thanks", "banter", "venting"):
        assert f"conversational.{cat}" in EXPRESSION_BANKS
        token = bind_voice_expression_state({})
        try:
            text = phrase_for_conversational_category(cat)
        finally:
            reset_voice_expression_state(token)
        assert text and len(text.split()) >= 2
