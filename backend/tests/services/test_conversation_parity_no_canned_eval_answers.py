"""Parity evidence must not be satisfied by prompt-specific production answer banks."""
from __future__ import annotations

import pytest

from app.services.conversational_turn_gate import (
    ambiguous_open_clarify_reply,
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
