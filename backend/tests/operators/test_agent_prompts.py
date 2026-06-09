from app.operators.agent_prompts import (
    AGENT_PERSONAS,
    get_agent_persona,
    normalize_agent_role,
)


def test_agent_personas_registry_includes_revenue_ops():
    assert "REVENUE_OPS" in AGENT_PERSONAS
    persona = AGENT_PERSONAS["REVENUE_OPS"]
    assert persona.display_name == "Revenue Operations Agent"
    assert "billing" in persona.system_prompt.lower()
    assert any("CRM" in item or "crm" in item.lower() for item in persona.expertise)


def test_get_agent_persona_from_revops_role():
    persona = get_agent_persona({"role": "RevOps", "name": "RevOps Bot"})
    assert persona.key == "REVENUE_OPS"


def test_get_agent_persona_from_department():
    persona = get_agent_persona({"department": "Revenue Operations", "name": "Ops"})
    assert persona.key == "REVENUE_OPS"


def test_get_agent_persona_config_override():
    persona = get_agent_persona({"role": "Sales", "config": {"persona": "REVENUE_OPS"}})
    assert persona.key == "REVENUE_OPS"


def test_get_agent_persona_seed_type_mapping():
    persona = get_agent_persona({"config": {"type": "revops"}, "name": "Seed"})
    assert persona.key == "REVENUE_OPS"


def test_normalize_sales_operations_alias():
    assert normalize_agent_role("Sales Operations") == "SALES"


def test_expanded_persona_copy_has_depth():
    for key in ("DEFAULT", "SALES", "MARKETING", "FINANCE", "HR", "CS", "DEVOPS", "REVENUE_OPS"):
        persona = AGENT_PERSONAS[key]
        assert len(persona.expertise) >= 4, key
        assert len(persona.heuristics) >= 4, key
        assert len(persona.constraints) >= 2, key
        assert len(persona.system_prompt) >= 80, key


def test_build_agent_system_prompt_includes_persona_sections():
    from app.operators.agent_prompts import build_agent_system_prompt

    prompt = build_agent_system_prompt(
        {"name": "Atlas", "role": "Marketing", "description": "Campaign ops"},
        org_context={"orgName": "Acme"},
        connected_integrations=["hubspot"],
    )
    assert "Marketing Agent" in prompt
    assert "Judgment heuristics:" in prompt
    assert "Constraints:" in prompt
    assert "hubspot" in prompt.lower()
