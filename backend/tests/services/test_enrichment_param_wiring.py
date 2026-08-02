"""Records + dollar-alias wiring for Clay→HubSpot enrichment workflows."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.clay_tools import CLAY_TOOL_EXECUTORS
from app.services.tool_service import params_for_step
from app.services.tool_types import ToolContext
from app.services.vertical_workflow_helper import enrich_msp_enrichment_parameters


def test_params_for_step_resolves_enriched_records_from_prior_outputs():
    params = params_for_step(
        "invoke_tool",
        {
            "action": "clay.crm.sync",
            "param_sources": {
                "records": "$enriched_records",
                "crm": "hubspot",
                "crm_connector_id": "$hubspot_connector_id",
            },
        },
        {"hubspot_connector_id": "hs-1"},
        step_outputs={
            "clay_outputs": {
                "records": [{"email": "a@b.com", "lastname": "A"}],
                "enriched_records": [{"email": "a@b.com", "lastname": "A"}],
            }
        },
    )
    assert params["records"] == [{"email": "a@b.com", "lastname": "A"}]
    assert params["crm_connector_id"] == "hs-1"
    assert params["crm"] == "hubspot"


def test_params_for_step_from_step_falls_back_when_contacts_empty():
    params = params_for_step(
        "invoke_tool",
        {
            "action": "clay.leads.push",
            "param_sources": {
                "records": {"from_step": "apollo_contacts_search", "path": ["records"]},
            },
        },
        {},
        step_outputs={
            "apollo_contacts_search": {"records": []},
            "apollo_people_search": {"records": [{"email": "p@x.com"}]},
        },
    )
    assert params["records"] == [{"email": "p@x.com"}]


def test_clay_leads_push_echoes_records_for_downstream_from_step():
    ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-clay",
        environment_name="production",
    )
    with (
        patch("app.services.clay_tools.enforce_rate_limit"),
        patch(
            "app.services.clay_tools.resolve_clay_connector",
            return_value=("conn-clay", "key", {"webhook_url": "https://example.com/hook"}),
        ),
        patch(
            "app.services.clay_tools.request_enrichment",
            return_value={"records_sent": 1},
        ),
    ):
        result = CLAY_TOOL_EXECUTORS["clay.leads.push"](
            ctx,
            {"records": [{"email": "a@b.com"}]},
        )
    assert result.success
    assert result.data["records"] == [{"email": "a@b.com"}]
    assert result.data["enriched_records"] == [{"email": "a@b.com"}]


def test_clay_workflows_output_get_passthrough_upstream_records():
    ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-clay",
        environment_name="production",
    )
    with (
        patch("app.services.clay_tools.enforce_rate_limit"),
        patch(
            "app.services.clay_tools.resolve_clay_connector",
            return_value=("conn-clay", "key", {}),
        ),
        patch(
            "app.services.clay_tools.pull_workflow_outputs",
            return_value={"outputs": [], "note": "no rows"},
        ),
    ):
        result = CLAY_TOOL_EXECUTORS["clay.workflows.output.get"](
            ctx,
            {"records": [{"email": "a@b.com", "lastname": "A"}]},
        )
    assert result.success
    assert result.data["records"] == [{"email": "a@b.com", "lastname": "A"}]
    assert result.data["record_count"] == 1


def test_enrich_msp_injects_hubspot_connector_id():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    with patch(
        "app.connectors.repository.get_connector_by_type",
        return_value={"id": "hs-conn-9"},
    ):
        out = enrich_msp_enrichment_parameters(
            {},
            {
                "id": "wf-1",
                "name": "MSP Prospects Clay Enrichment → HubSpot Sync",
                "config": {"workflow_slug": "msp-prospects-clay-hubspot-enrichment"},
            },
            client=client,
            org_id="org-1",
            environment_name="production",
        )
    assert out["hubspot_connector_id"] == "hs-conn-9"
