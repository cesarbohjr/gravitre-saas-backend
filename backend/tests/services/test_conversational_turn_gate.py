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
