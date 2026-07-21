"""Unit tests for conversational vs task-shaped turn gate."""
from __future__ import annotations

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
