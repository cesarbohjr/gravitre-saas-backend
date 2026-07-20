"""HR & Talent Intelligence Pack unit tests (scaffold — no live OAuth)."""
from __future__ import annotations

from app.marketplace.connector_category_templates import CONNECTOR_CATEGORY_TEMPLATES
from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec, list_intelligence_pack_specs
from app.services.tool_service import list_registered_actions


def test_hr_talent_intelligence_pack_demo_in_catalog():
    spec = get_intelligence_pack_spec("hr-talent-intelligence-pack")
    assert spec is not None
    assert spec.demo_agent_name == "Recruiting Talent Analyst"
    assert spec.connector_template_id == "hr-talent-intelligence-sources"
    assert set(spec.demo_systems or []) >= {"workday", "bamboohr", "greenhouse", "gusto"}
    actions = {s.get("config", {}).get("action") for s in (spec.workflow_steps or [])}
    assert "greenhouse.jobs.list" in actions
    assert "hr-talent-intelligence-pack" in {s.pack_id for s in list_intelligence_pack_specs()}


def test_hr_talent_intelligence_sources_template():
    tpl = CONNECTOR_CATEGORY_TEMPLATES["hr-talent-intelligence-sources"]
    assert set(tpl["connectors"]) == {"workday", "bamboohr", "greenhouse", "gusto"}


def test_hr_talent_demo_actions_registered():
    registered = set(list_registered_actions())
    assert "greenhouse.jobs.list" in registered
    assert "bamboohr.employees.list" in registered
    assert "workday.orgunits.list" in registered
    assert "gusto.companies.get" in registered
