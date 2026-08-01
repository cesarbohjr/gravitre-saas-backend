"""MSP pack + catalog unit tests."""
from __future__ import annotations

from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec, list_intelligence_pack_specs
from app.marketplace.workflows.msp_prospecting_list_workflow import WORKFLOW_NAME
from app.services.tool_service import list_registered_actions


def test_msp_intelligence_pack_demo_in_catalog():
    spec = get_intelligence_pack_spec("msp-intelligence-pack")
    assert spec is not None
    assert spec.demo_agent_name == "MSP Prospecting Coordinator"
    assert spec.connector_template_id == "msp-intelligence-sources"
    assert "apollo" in (spec.demo_systems or [])
    assert "hubspot" in (spec.demo_systems or [])
    assert "nvd" in (spec.demo_systems or [])
    assert spec.workflow_name == WORKFLOW_NAME
    actions = {s.get("config", {}).get("action") for s in spec.workflow_steps if s.get("type") == "invoke_tool"}
    assert "apollo.organizations.search" in actions
    assert "apollo.lists.create" in actions
    assert "hubspot.lists.create" in actions
    assert any(s.get("type") == "agent" for s in spec.workflow_steps)
    assert any(a.source_id == "nvd-cve-feed" for a in spec.assignments)
    assert any(a.source_id == "msp-icp-criteria" for a in spec.assignments)
    slugs = {s.pack_id for s in list_intelligence_pack_specs()}
    assert "msp-intelligence-pack" in slugs


def test_nvd_cve_get_registered():
    assert "nvd.cve.get" in set(list_registered_actions())
