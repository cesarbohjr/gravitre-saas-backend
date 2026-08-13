"""Expert dialogue library — composition with Module D + spoken register."""
from __future__ import annotations

from app.operators.agent_intelligence import get_agent_intelligence
from app.services.expert_dialogue_library import (
    expert_dialogue_prompt_section,
    resolve_expert_department,
)
from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt


def test_resolve_seo_marketing_analyst_to_marketing():
    agent = {
        "name": "SEO Marketing Analyst",
        "department": "marketing",
        "role": "analyst",
    }
    assert resolve_expert_department(agent) == "marketing"
    section = expert_dialogue_prompt_section(agent)
    assert "Expert dialogue examples (marketing)" in section
    assert "INVALID_PROPERTY" in section or "pipeline-scoped" in section
    assert "Gravitre-authored" in section


def test_sales_and_finance_sections_grounded():
    sales = expert_dialogue_prompt_section({"name": "Sales Agent", "department": "sales"})
    finance = expert_dialogue_prompt_section({"name": "Finance", "department": "finance"})
    assert "Opportunity" in sales or "champion" in sales
    assert "PaymentIntent" in finance or "idempotency" in finance


def test_legal_hr_cyber_sections_pilot_depth():
    legal = expert_dialogue_prompt_section({"name": "Legal Agent", "department": "legal"})
    hr = expert_dialogue_prompt_section({"name": "HR Agent", "department": "hr"})
    cyber = expert_dialogue_prompt_section(
        {"name": "Cybersecurity Agent", "department": "cybersecurity"}
    )
    assert "written release" in legal.lower() or "attestation" in legal.lower()
    assert "governing law" in legal.lower() or "residual" in legal.lower()
    assert "scorecard" in hr.lower() or "adverse" in hr.lower()
    assert "phishing-resistant" in cyber.lower() or "bastion" in cyber.lower()
    assert "mfa" in cyber.lower()


def test_module_d_prompt_includes_expert_dialogue_for_marketing_agent():
    agent = {"id": "a1", "name": "Marketing Analyst", "department": "marketing"}
    text = build_module_d_unified_system_prompt(agent=agent, spoken_mode=False)
    assert "Expert dialogue examples (marketing)" in text
    assert "Register 1" in text or "CONVERSATIONAL" in text
    assert "Conversational behavior" in text


def test_spoken_mode_stacks_expert_and_spoken_register():
    agent = {"id": "a1", "name": "Sales Agent", "department": "sales"}
    text = build_module_d_unified_system_prompt(agent=agent, spoken_mode=True)
    assert "Expert dialogue examples (sales)" in text
    assert "SPOKEN" in text
    assert "drop markdown" in text.lower() or "spoken" in text.lower()


def test_classical_prompt_includes_expert_dialogue():
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
    assert "Expert dialogue examples (marketing)" in prompt
