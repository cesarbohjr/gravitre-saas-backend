"""Sales pack unit tests."""
from __future__ import annotations

from app.marketplace.connector_category_templates import CONNECTOR_CATEGORY_TEMPLATES
from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec, list_intelligence_pack_specs
from app.services.tool_service import list_registered_actions


def test_sales_intelligence_pack_demo_in_catalog():
    spec = get_intelligence_pack_spec("sales-intelligence-pack")
    assert spec is not None
    assert spec.demo_agent_name == "Sales Pipeline Analyst"
    assert spec.connector_template_id == "sales-intelligence-sources"
    assert "hubspot" in (spec.demo_systems or [])
    assert any(s.get("config", {}).get("action") == "hubspot.pipelines.list" for s in spec.workflow_steps)
    assert any(a.source_id == "hubspot-pipeline" for a in spec.assignments)
    assert "msp-intelligence-pack" in {s.pack_id for s in list_intelligence_pack_specs()}


def test_sales_intelligence_sources_template():
    tpl = CONNECTOR_CATEGORY_TEMPLATES["sales-intelligence-sources"]
    assert "hubspot" in tpl["connectors"]
    assert "apollo" in tpl["connectors"]
    assert "crunchbase" not in tpl["connectors"]
    assert "zoominfo" not in tpl["connectors"]


def test_hubspot_pipelines_list_registered():
    assert "hubspot.pipelines.list" in set(list_registered_actions())
