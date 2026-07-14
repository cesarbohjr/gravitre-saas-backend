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
    actions = {s.get("config", {}).get("action") for s in spec.workflow_steps}
    assert "apollo.organizations.search" in actions
    assert "apollo.people.search" in actions
    assert "apollo.lists.create" in actions
    assert "hubspot.lists.create" in actions
    assert "prospecting-intelligence-pack" in {s.pack_id for s in list_intelligence_pack_specs()}
    # STA-312: enrichment assignment is gated knowledge, not a live Crunchbase/PDL source
    gated = [a for a in spec.assignments if a.source_id == "account-enrichment-gated"]
    assert gated and "STA-312" in (gated[0].reference_summary or "")


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
    assert "hubspot.lists.create" in registered


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
