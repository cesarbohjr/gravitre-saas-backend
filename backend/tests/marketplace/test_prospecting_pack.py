"""Prospecting pack unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.connector_category_templates import CONNECTOR_CATEGORY_TEMPLATES
from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec, list_intelligence_pack_specs
from app.services.tool_service import list_registered_actions


def test_prospecting_pack_demo_in_catalog():
    spec = get_intelligence_pack_spec("prospecting-intelligence-pack")
    assert spec is not None
    assert spec.demo_agent_name == "Lead Scouting Analyst"
    assert spec.connector_template_id == "prospecting-intelligence-sources"
    assert "apollo" in (spec.demo_systems or [])
    assert "clay" in (spec.demo_systems or [])
    actions = {s.get("config", {}).get("action") for s in spec.workflow_steps}
    assert "apollo.organizations.search" in actions
    assert "apollo.people.search" in actions
    assert "apollo.lists.create" in actions
    assert "hubspot.lists.create" in actions
    assert "prospecting-intelligence-pack" in {s.pack_id for s in list_intelligence_pack_specs()}
    # PDL BYO knowledge assignment; Memory/KG contact writes still STA-312 gated
    pdl = [a for a in spec.assignments if a.source_id == "pdl-account-enrichment"]
    assert pdl and "STA-312" in (pdl[0].reference_summary or "")
    assert "dashboard.peopledatalabs.com" in (pdl[0].external_url or "")
    clay = [a for a in spec.assignments if a.source_id == "clay-list-enrichment"]
    assert clay and "clay.leads.push" in (clay[0].reference_summary or "")


def test_prospecting_enrichment_workflow_definition():
    from app.marketplace.workflows.msp_enrichment_workflow import (
        WORKFLOW_NAME,
        build_msp_enrichment_workflow_steps,
    )

    steps = build_msp_enrichment_workflow_steps()
    assert len(steps) == 10
    assert steps[0]["config"]["action"] == "apollo.lists.list"
    assert steps[1]["config"]["action"] == "apollo.contacts.search"
    actions = [(s.get("config") or {}).get("action") for s in steps if s.get("type") == "invoke_tool"]
    assert "apollo.lists.add" in actions
    assert "hubspot.lists.add_contact" in actions
    assert steps[-1]["type"] == "agent"
    assert "MSP Prospects" in WORKFLOW_NAME or "Clay" in WORKFLOW_NAME


@patch("app.operators.repository.create_operator")
@patch("app.marketplace.intelligence_packs.prospecting_install.install_intelligence_pack")
@patch("app.marketplace.intelligence_packs.prospecting_install.install_connector_category_template")
def test_prospecting_install_includes_enrichment_workflow(
    mock_template,
    mock_install_pack,
    mock_create_operator,
):
    from app.marketplace.intelligence_packs.prospecting_install import install_prospecting_pack_demo_bundle

    mock_install_pack.return_value = {"count": 5, "assignments": [{"id": "a1"}]}
    mock_template.return_value = {"created": [], "stagedCount": 0, "skipped": []}
    mock_create_operator.return_value = {"id": "op-1"}

    upserts: list[dict] = []

    def _table(name: str):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.is_.return_value = mock
        mock.limit.return_value = mock
        mock.insert.return_value = mock
        mock.execute.side_effect = lambda: MagicMock(error=None, data=[{"id": "node-1"}])
        mock.upsert.side_effect = lambda row, **kwargs: upserts.append({"table": name, "row": row}) or mock
        return mock

    client = MagicMock()
    client.table.side_effect = _table

    spec = get_intelligence_pack_spec("prospecting-intelligence-pack")
    assert spec
    bundle = install_prospecting_pack_demo_bundle(
        client,
        "org-1",
        {"id": "asset-1"},
        spec,
        actor_id="user-1",
    )

    assert bundle.get("enrichmentWorkflowId")
    assert bundle.get("workflowId")
    workflow_names = [
        row["row"].get("name")
        for row in upserts
        if row["table"] == "workflow_defs"
    ]
    assert "Prospecting Apollo Lead Scout" in workflow_names
    assert any("Clay Enrichment" in str(name) for name in workflow_names)


def test_prospecting_sources_template_excludes_governance_vendors():
    tpl = CONNECTOR_CATEGORY_TEMPLATES["prospecting-intelligence-sources"]
    assert "apollo" in tpl["connectors"]
    assert "hubspot" in tpl["connectors"]
    assert "crunchbase" not in tpl["connectors"]
    assert "pdl" not in tpl["connectors"]
    assert "zoominfo" not in tpl["connectors"]
    byo = CONNECTOR_CATEGORY_TEMPLATES["byo-premium-prospecting"]
    assert "zoominfo" in byo["connectors"]
    assert "linkedin_sales_navigator" in byo["connectors"]


def test_prospecting_demo_actions_registered():
    registered = set(list_registered_actions())
    assert "apollo.organizations.search" in registered
    assert "apollo.lists.create" in registered
    assert "apollo.lists.list" in registered
    assert "apollo.lists.add" in registered
    assert "apollo.contacts.search" in registered
    assert "hubspot.lists.create" in registered
    assert "clay.leads.push" in registered
    assert "clay.crm.sync" in registered


def test_apollo_lists_create_result_url():
    from types import SimpleNamespace

    from app.services.apollo_tools import _exec_lists_create
    from app.services.tool_types import ToolContext

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="actor-1",
    )
    with (
        patch("app.services.apollo_tools._session", return_value=("conn-a", {"Authorization": "Bearer x"})),
        patch(
            "app.services.apollo_tools.create_label",
            return_value={"label": {"id": "42", "name": "Scout"}},
        ),
        patch("app.services.intelligence_pack_tools.emit_pack_source_notification") as emit,
    ):
        result = _exec_lists_create(ctx, {"name": "Scout", "modality": "contacts"})
    assert result.success is True
    assert "app.apollo.io" in (result.data.get("result_url") or "")
    emit.assert_called_once()
    assert emit.call_args.kwargs["action"] == "apollo.lists.create"
