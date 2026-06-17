"""MKT-3.1 / MKT-9.5: marketplace asset schema validation."""
from __future__ import annotations

import pytest

from app.marketplace.schemas import (
    MarketplaceValidationError,
    find_forbidden_secret_paths,
    parse_asset_config,
    validate_asset_payload,
    validate_install_variables,
)
from app.workflows.constants import SCHEMA_VERSION


def _valid_workflow_config() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": "Inbound lead qualification",
        "description": "HubSpot lookup and agent scoring",
        "steps": [
            {
                "id": "lookup",
                "name": "HubSpot lookup",
                "type": "invoke_tool",
                "config": {"action": "hubspot.search_contacts"},
            },
            {
                "id": "qualify",
                "name": "Qualify lead",
                "type": "agent",
                "metadata": {"task": "Score lead fit"},
            },
        ],
    }


def test_parse_agent_asset_config():
    parsed = parse_asset_config(
        "ai_agent",
        {
            "name": "Lead Qualifier Agent",
            "purpose": "Scores inbound leads",
            "role": "Sales Development",
            "systems": ["hubspot"],
        },
    )
    assert parsed.name == "Lead Qualifier Agent"


def test_parse_workflow_asset_config_uses_workflow_validator():
    parsed = parse_asset_config("workflow", _valid_workflow_config())
    assert parsed.schema_version == SCHEMA_VERSION
    assert len(parsed.steps) == 2


def test_rejects_unknown_workflow_step_type():
    config = _valid_workflow_config()
    config["steps"][0]["type"] = "not_a_real_step"
    with pytest.raises(MarketplaceValidationError) as exc:
        parse_asset_config("workflow", config)
    assert any("invalid" in err or "unsupported" in err for err in exc.value.errors)


def test_rejects_secret_fields_in_config():
    with pytest.raises(MarketplaceValidationError) as exc:
        parse_asset_config(
            "connector_config",
            {
                "connector_type": "hubspot",
                "label": "HubSpot",
                "access_token": "secret-value",
            },
        )
    assert any("forbidden_secret" in err for err in exc.value.errors)


def test_find_forbidden_secret_paths_nested():
    paths = find_forbidden_secret_paths(
        {"metadata": {"client_secret": "x", "safe": {"refresh_token": "y"}}}
    )
    assert "metadata.client_secret" in paths
    assert "metadata.safe.refresh_token" in paths


def test_validate_install_variables_normalizes_keys():
    parsed = validate_install_variables(
        [{"key": "hubspot_portal", "label": "HubSpot portal ID", "required": True}]
    )
    assert parsed[0].key == "HUBSPOT_PORTAL"


def test_validate_install_variables_rejects_duplicate_keys():
    with pytest.raises(MarketplaceValidationError):
        validate_install_variables(
            [
                {"key": "PORTAL", "label": "One", "required": True},
                {"key": "portal", "label": "Two", "required": False},
            ]
        )


def test_validate_asset_payload_round_trip():
    payload = validate_asset_payload(
        asset_type="department_pack",
        config={
            "workflow_name": "Sales pack workflow",
            "workflow_description": "Lead flow",
            "agents": [
                {
                    "name": "Lead Qualifier Agent",
                    "purpose": "Scores leads",
                }
            ],
            "rag_sources": [{"title": "Sales Playbook"}],
            "workflow_steps": _valid_workflow_config()["steps"],
        },
        install_variables=[{"key": "TEAM_NAME", "label": "Team name", "required": True}],
        required_connectors=[{"connectorType": "hubspot", "label": "HubSpot"}],
        publish=True,
    )
    assert payload["install_variables"][0]["key"] == "TEAM_NAME"
    assert payload["required_connectors"][0]["connectorType"] == "hubspot"


def test_publish_gate_revalidates_invalid_department_pack():
    with pytest.raises(MarketplaceValidationError):
        validate_asset_payload(
            asset_type="department_pack",
            config={
                "workflow_name": "Broken",
                "agents": [{"name": "Agent"}],
                "workflow_steps": [{"id": "x", "name": "Bad", "type": "unknown_type"}],
            },
            publish=True,
        )
