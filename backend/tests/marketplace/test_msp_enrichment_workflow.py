"""Tests for MSP Prospects Clay → HubSpot enrichment workflow catalog definition."""
from __future__ import annotations

from app.marketplace.schemas import parse_asset_config, validate_asset_payload
from app.marketplace.workflows.msp_enrichment_workflow import (
    AGENT_SLUG,
    WORKFLOW_SLUG,
    build_msp_enrichment_workflow_steps,
)
from app.workflows.constants import SCHEMA_VERSION
from app.workflows.schema import validate_definition


def test_msp_enrichment_workflow_steps_validate():
    steps = build_msp_enrichment_workflow_steps()
    definition = validate_definition({"schema_version": SCHEMA_VERSION, "steps": steps})
    assert len(definition["steps"]) == 7
    step_types = [step["type"] for step in steps]
    assert step_types.count("invoke_tool") == 5
    assert step_types.count("agent") == 2


def test_msp_enrichment_workflow_tool_actions_registered():
    steps = build_msp_enrichment_workflow_steps()
    actions = [
        step["config"]["action"]
        for step in steps
        if step.get("type") == "invoke_tool"
    ]
    assert actions == [
        "apollo.lists.list",
        "apollo.contacts.search",
        "clay.leads.push",
        "clay.workflows.output.get",
        "clay.crm.sync",
    ]


def test_msp_enrichment_workflow_agent_seed():
    steps = build_msp_enrichment_workflow_steps()
    agent_steps = [step for step in steps if step.get("type") == "agent"]
    assert all(step["metadata"]["agent_seed"] == f"agent:{AGENT_SLUG}" for step in agent_steps)
    assert agent_steps[0]["metadata"].get("briefing_from_steps") is True
    assert "apollo.lists.add" in agent_steps[0]["metadata"]["task"]
    assert "apollo.people.search" in agent_steps[0]["metadata"]["task"]


def test_msp_enrichment_workflow_catalog_asset_parses():
    from app.marketplace.seed_catalog import catalog_assets_by_slug

    asset = catalog_assets_by_slug()[WORKFLOW_SLUG]
    assert asset.asset_type == "workflow"
    assert {c["connectorType"] for c in asset.required_connectors} == {"apollo", "clay", "hubspot"}
    parsed = parse_asset_config("workflow", asset.config)
    assert len(parsed.steps) == 7
    validated = validate_asset_payload(
        asset_type="workflow",
        config=asset.config,
        install_variables=asset.install_variables,
        required_connectors=asset.required_connectors,
        publish=True,
    )
    assert validated["install_variables"][1]["key"] == "HUBSPOT_LIST_ID"
