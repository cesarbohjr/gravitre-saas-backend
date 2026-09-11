"""The voice fault probe must be unreachable for any real org.

A deliberate fault path in production code is only acceptable if the gate is
provably tight, so the gate gets tested harder than the fault itself.
"""

from __future__ import annotations

import uuid

from app.services.composer_failure_triggers import (
    VOICE_TURN_FAILURE_CONVERSATION_ID,
    VOICE_TURN_FAILURE_MESSAGE,
    is_voice_turn_failure_probe,
)
from app.services.conversation_write_guard import is_isolated_conversation_test_org

ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"


def test_isolated_org_with_the_sentinel_conversation_fires() -> None:
    assert is_isolated_conversation_test_org(ISOLATED_ORG), (
        "test premise: this org must be the isolated smoke org"
    )
    assert is_voice_turn_failure_probe(
        org_id=ISOLATED_ORG, conversation_id=VOICE_TURN_FAILURE_CONVERSATION_ID
    )


def test_a_real_org_cannot_reach_it_even_with_the_sentinel() -> None:
    """The org gate is the load-bearing half: the sentinel id is guessable."""
    for org in (str(uuid.uuid4()), "", None, ISOLATED_ORG.replace("1501", "1502")):
        assert not is_voice_turn_failure_probe(
            org_id=org, conversation_id=VOICE_TURN_FAILURE_CONVERSATION_ID
        ), f"org {org!r} must not reach the fault path"


def test_isolated_org_normal_conversations_are_untouched() -> None:
    """Ordinary smoke traffic must not start raising."""
    for conv in (str(uuid.uuid4()), "", None, VOICE_TURN_FAILURE_CONVERSATION_ID + "x"):
        assert not is_voice_turn_failure_probe(org_id=ISOLATED_ORG, conversation_id=conv)


def test_sentinel_match_is_case_and_whitespace_tolerant() -> None:
    for variant in (
        VOICE_TURN_FAILURE_CONVERSATION_ID.upper(),
        f"  {VOICE_TURN_FAILURE_CONVERSATION_ID}  ",
    ):
        assert is_voice_turn_failure_probe(org_id=ISOLATED_ORG, conversation_id=variant)


def test_probe_message_is_detected_as_raw_backend_text() -> None:
    """If this ever reaches a user, the leak scan must catch it.

    The probe exists to prove raw text does not escape, so a message the
    detector considers clean would make the verification vacuous.
    """
    from app.services.response_composer import looks_like_raw_backend

    assert looks_like_raw_backend(VOICE_TURN_FAILURE_MESSAGE)
