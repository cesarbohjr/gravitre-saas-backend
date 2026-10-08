"""Conversation DNA regression coverage: additive guidance and consistent identity."""

from app.services.pipecat_voice.conversation_dna import (
    CORE_VOICE_IDENTITY,
    TIER_VOICE_GUIDANCE,
    build_voice_conversation_guidance,
)


def test_voice_guidance_has_same_core_for_all_tiers():
    assert set(TIER_VOICE_GUIDANCE) == {"light", "medium", "deep"}
    for utterance in ("Hello!", "How does onboarding work?", "Investigate production logs"):
        assert build_voice_conversation_guidance(utterance).startswith(CORE_VOICE_IDENTITY)


def test_voice_guidance_preserves_existing_persona_and_safety():
    text = build_voice_conversation_guidance("Hello!")
    assert "selected agent persona" in text
    assert "dialogue preferences" in text
    assert "tool permissions" in text


def test_deep_remains_governed_and_light_no_unsolicited_account_data():
    assert "approval gates" in build_voice_conversation_guidance("Investigate production logs")
    assert "Do not volunteer account details" in build_voice_conversation_guidance("Hello!")
