"""Shared conversational-behavior layer — composition with Module D + classical."""
from __future__ import annotations

from app.operators.agent_intelligence import RULES_SECTION, get_agent_intelligence
from app.services.conversational_behavior import (
    CONVERSATIONAL_BEHAVIOR_SECTION,
    conversational_behavior_section,
)
from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt


def test_conversational_behavior_section_has_ten_rules_and_honesty():
    text = conversational_behavior_section()
    assert text == CONVERSATIONAL_BEHAVIOR_SECTION
    assert "Ask before assuming" in text
    assert "Reference prior turns" in text
    assert "Vary response shape" in text
    assert "Don't over-answer" in text or "Dont over-answer" in text or "over-answer" in text.lower()
    assert "Hold a real position" in text
    assert "Corrections persist" in text
    assert "Push back when warranted" in text
    assert "Avoid scripted-assistant patterns" in text
    assert "Default to brief" in text
    assert "Meet the human moment" in text
    assert "NEVER invent" in text or "never invent" in text.lower()
    assert "Want me to schedule it for review" in text


def test_module_d_live_prompt_includes_conversational_behavior():
    agent = {"id": "a1", "name": "SEO Marketing Analyst", "department": "marketing"}
    text = build_module_d_unified_system_prompt(agent=agent)
    assert "## Conversational behavior" in text
    assert "Don't over-answer" in text or "over-answer" in text.lower()
    assert "organic traffic for the main site" in text.lower()
    assert "Knowledge boundaries" in text or "anti-fabrication" in text.lower()
    # Distinct from register system — both present
    assert "Register 1" in text or "CONVERSATIONAL" in text


def test_classical_system_prompt_includes_conversational_behavior():
    intel = get_agent_intelligence()
    agent = {
        "id": "a1",
        "name": "SEO Marketing Analyst",
        "role": "analyst",
        "department": "marketing",
        "purpose": "SEO briefing",
        "config": {},
    }
    prompt = intel._build_system_prompt(
        "agent_chat",
        agent,
        rag_results=[],
        org_context={"name": "Acme"},
    )
    assert "## Conversational behavior" in prompt
    assert "## Voice" in prompt
    assert "Ask for clarification" in RULES_SECTION
