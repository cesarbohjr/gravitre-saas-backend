"""Conversation DNA regression coverage: one character, tier overlay, persona first.

Ported from the earlier restore attempt. The builder now takes the tier (decided
once per turn by the history-aware classifier) instead of re-deriving it from the
latest text, and precedence is stated once in the core instead of per tier.
"""

from app.services.pipecat_voice.conversation_dna import (
    CONVERSATION_DNA_CORE,
    TIER_OVERLAYS,
    build_conversation_dna_section,
)


def test_voice_guidance_has_same_core_for_all_tiers():
    assert set(TIER_OVERLAYS) == {"light", "medium", "deep"}
    for tier in ("light", "medium", "deep"):
        assert build_conversation_dna_section(tier).startswith(CONVERSATION_DNA_CORE)


def test_voice_guidance_defers_to_persona_and_rules():
    text = build_conversation_dna_section("light")
    assert "persona, response style and rules elsewhere in this prompt win on any conflict" in text


def test_deep_remains_governed_and_light_no_unsolicited_account_data():
    assert "respect approvals" in build_conversation_dna_section("deep")
    assert "Never volunteer account, CRM or connector data" in build_conversation_dna_section("light")
    assert "No tools or business lookups unless they ask" in build_conversation_dna_section("light")
