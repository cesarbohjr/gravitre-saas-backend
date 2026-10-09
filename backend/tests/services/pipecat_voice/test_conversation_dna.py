"""Conversation DNA placement, precedence and size on both brain prompt builders."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.operators.agent_intelligence import AgentIntelligence
from app.services.module_d_unified_voice_spec import (
    build_module_d_unified_system_prompt,
)
from app.services.pipecat_voice.conversation_dna import (
    CONVERSATION_DNA_CORE,
    TEXT_DNA_CORE,
    TIER_OVERLAYS,
    build_conversation_dna_section,
)

DNA_HEADER = "## Conversation character (voice)"
TEXT_DNA_HEADER = "## Conversation character (text)"


def test_every_tier_inherits_the_same_core() -> None:
    assert set(TIER_OVERLAYS) == {"light", "medium", "deep"}
    for tier in ("light", "medium", "deep"):
        section = build_conversation_dna_section(tier)
        assert section.startswith(CONVERSATION_DNA_CORE)
        assert section.endswith(TIER_OVERLAYS[tier])


def test_length_budget_under_900_chars_per_turn() -> None:
    for tier in ("light", "medium", "deep", None, "bogus"):
        assert len(build_conversation_dna_section(tier)) < 900


def test_unknown_tier_reads_as_medium() -> None:
    assert build_conversation_dna_section(None) == build_conversation_dna_section("medium")
    assert build_conversation_dna_section("nope") == build_conversation_dna_section("medium")


def test_core_states_precedence_and_boundaries() -> None:
    core = CONVERSATION_DNA_CORE
    assert "win on any conflict" in core
    assert "Never claim to be human" in core
    assert "Never volunteer account, CRM or connector data" in core
    assert "never at their expense" in core
    assert "No tools or business lookups unless they ask" in TIER_OVERLAYS["light"]
    assert "respect approvals" in TIER_OVERLAYS["deep"]


def test_fewshot_hook_appends_last_and_ignores_blank() -> None:
    base = build_conversation_dna_section("light")
    assert build_conversation_dna_section("light", fewshot_block="   ") == base
    with_shots = build_conversation_dna_section("light", fewshot_block="User: hi\nAssistant: hey!")
    assert with_shots.startswith(base)
    assert with_shots.endswith("User: hi\nAssistant: hey!")


# --- unified LIVE (Module D) prompt -------------------------------------------------


def test_module_d_spoken_prompt_places_dna_after_persona_and_before_policy() -> None:
    agent = {"id": "agent-1", "name": "Ava", "config": {"response_style": "support_specialist"}}
    prompt = build_module_d_unified_system_prompt(
        spoken_mode=True,
        include_few_shots=False,
        agent=agent,
        extra_operator_rules="## Voice\nOPERATOR RULES SENTINEL",
        conversation_tier="light",
    )
    assert prompt.count(DNA_HEADER) == 1
    dna = prompt.index(DNA_HEADER)
    assert prompt.index("## Response style") < dna
    assert prompt.index("Register 5 — SPOKEN") < dna
    # Operator rules (and anything appended after them) still come last.
    assert dna < prompt.index("OPERATOR RULES SENTINEL")
    assert TIER_OVERLAYS["light"] in prompt


def test_module_d_typed_prompt_gets_text_character_not_voice() -> None:
    prompt = build_module_d_unified_system_prompt(spoken_mode=False, conversation_tier="deep")
    assert DNA_HEADER not in prompt
    assert prompt.count(TEXT_DNA_HEADER) == 1
    assert TIER_OVERLAYS["deep"] in prompt


def test_module_d_typed_prompt_without_tier_has_no_dna() -> None:
    prompt = build_module_d_unified_system_prompt(spoken_mode=False)
    assert DNA_HEADER not in prompt and TEXT_DNA_HEADER not in prompt


def test_module_d_only_overlay_varies_between_tiers() -> None:
    light = build_module_d_unified_system_prompt(spoken_mode=True, include_few_shots=False, conversation_tier="light")
    deep = build_module_d_unified_system_prompt(spoken_mode=True, include_few_shots=False, conversation_tier="deep")
    assert light.replace(TIER_OVERLAYS["light"], "") == deep.replace(TIER_OVERLAYS["deep"], "")


# --- classical prompt builder ------------------------------------------------------


@pytest.fixture
def intelligence() -> AgentIntelligence:
    settings = SimpleNamespace(
        disable_ai=False,
        rag_top_k=5,
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
    )
    return AgentIntelligence(
        settings=settings, react_engine=MagicMock(), rag_service=MagicMock(), unified_retrieval=MagicMock()
    )


def test_classical_spoken_prompt_keeps_persona_first_and_policy_last(intelligence: AgentIntelligence) -> None:
    prompt = intelligence._build_system_prompt(
        "assistant",
        None,
        [],
        {},
        assistant_base_prompt="PERSONA SENTINEL",
        spoken_mode=True,
        spoken_user_text="haha nice",
        task_state_section="TASK STATE SENTINEL",
        conversation_tier="light",
    )
    assert prompt.count(DNA_HEADER) == 1
    dna = prompt.index(DNA_HEADER)
    assert prompt.index("PERSONA SENTINEL") < dna
    assert prompt.index("## Response style") < dna
    assert prompt.index("Register 5 — SPOKEN") < dna
    assert dna < prompt.index("TASK STATE SENTINEL")
    assert dna < prompt.index("## Research Policy")
    assert dna < prompt.index("## Rules")
    assert TIER_OVERLAYS["light"] in prompt


def test_classical_agent_prompt_also_carries_dna(intelligence: AgentIntelligence) -> None:
    agent = {"id": "agent-1", "name": "Ava", "config": {}}
    prompt = intelligence._build_system_prompt("agent_chat", agent, [], {}, spoken_mode=True, conversation_tier="deep")
    assert DNA_HEADER in prompt
    assert TIER_OVERLAYS["deep"] in prompt


def test_classical_typed_prompt_gets_text_character(intelligence: AgentIntelligence) -> None:
    prompt = intelligence._build_system_prompt(
        "assistant",
        None,
        [],
        {},
        assistant_base_prompt="PERSONA SENTINEL",
        spoken_user_text="haha tell me a joke",
        task_state_section="TASK STATE SENTINEL",
        conversation_tier="light",
    )
    assert DNA_HEADER not in prompt
    assert prompt.count(TEXT_DNA_HEADER) == 1
    dna = prompt.index(TEXT_DNA_HEADER)
    assert prompt.index("PERSONA SENTINEL") < dna < prompt.index("TASK STATE SENTINEL")
    assert dna < prompt.index("## Rules")
    assert TIER_OVERLAYS["light"] in prompt


def test_text_core_keeps_the_same_boundaries() -> None:
    assert TEXT_DNA_CORE.startswith(TEXT_DNA_HEADER)
    for phrase in ("win on any conflict", "Never claim to be human",
                   "Never volunteer account, CRM or connector data", "never at their expense"):
        assert phrase in TEXT_DNA_CORE
    text = build_conversation_dna_section("deep", spoken=False)
    assert text.startswith(TEXT_DNA_CORE) and text.endswith(TIER_OVERLAYS["deep"])
    assert len(text) < 900


def test_conversational_tiers_get_library_style_examples() -> None:
    from app.services.pipecat_voice.conversation_dna import conversation_dna_for_turn
    from app.services.pipecat_voice.dialogue_library import HEADER

    light = conversation_dna_for_turn("light", "haha tell me a joke")
    assert light.startswith(build_conversation_dna_section("light"))
    assert HEADER in light
    assert len(light) < 900 + 700


def test_deep_turns_get_one_narrative_example_and_empty_turns_none() -> None:
    from app.services.pipecat_voice.conversation_dna import conversation_dna_for_turn
    from app.services.pipecat_voice.dialogue_library import HEADER

    deep = conversation_dna_for_turn("deep", "pull my pipeline")
    assert deep.startswith(build_conversation_dna_section("deep"))
    assert HEADER in deep and deep.count("\n\nUser:") == 1
    assert "what it means, then the next step" in TIER_OVERLAYS["deep"]
    assert conversation_dna_for_turn("light", "  ") == build_conversation_dna_section("light")


def test_module_d_spoken_prompt_carries_style_examples_for_light_turns() -> None:
    from app.services.pipecat_voice.dialogue_library import HEADER

    prompt = build_module_d_unified_system_prompt(
        spoken_mode=True,
        include_few_shots=False,
        conversation_tier="light",
        spoken_user_text="haha that's funny",
    )
    assert HEADER in prompt
