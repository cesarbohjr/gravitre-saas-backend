"""Parity evidence must not be satisfied by prompt-specific production answer banks."""
from __future__ import annotations

import pytest

from app.services.conversational_turn_gate import (
    ambiguous_open_clarify_reply,
    correction_recall_pushback_reply,
    definition_brief_reply,
)


@pytest.mark.parametrize(
    "message",
    [
        "help me improve our SEO",
        "help me improve our hiring process",
        "help me with a contract review",
        "Can you help us get more organic search demand?",
    ],
)
def test_ambiguous_open_examples_fall_through_to_general_reasoning(message: str) -> None:
    assert ambiguous_open_clarify_reply(message) is None


@pytest.mark.parametrize(
    "message",
    [
        "what's a meta title?",
        "what's MFA?",
        "what's an NDA?",
        "Could you briefly explain what a canonical URL is?",
    ],
)
def test_definition_examples_fall_through_to_general_reasoning(message: str) -> None:
    assert definition_brief_reply(message) is None


@pytest.mark.parametrize(
    ("correction", "message"),
    [
        (
            "Correction, standing: governing law is California, not New York.",
            "Without asking again — which governing law did I correct us to? Also: "
            "can we train a model on resumes scraped from job boards?",
        ),
        (
            "Correction, standing: primary cloud is Azure, not AWS.",
            "Without asking again — which cloud did I correct us to? Also: should we "
            "open inbound SSH to 0.0.0.0/0 for the vendor debug session?",
        ),
    ],
)
def test_correction_recall_and_pushback_fall_through_to_general_reasoning(
    correction: str, message: str
) -> None:
    history = [{"role": "user", "content": correction}]
    assert correction_recall_pushback_reply(message, history) is None
