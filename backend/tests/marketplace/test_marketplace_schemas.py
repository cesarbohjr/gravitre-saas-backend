"""MKT-3.1 / MKT-9.5: marketplace asset schema validation."""
from __future__ import annotations

import pytest

from app.marketplace.schemas import (
    FORBIDDEN_SECRET_KEYS,
    MarketplaceValidationError,
    assert_no_forbidden_secrets,
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


@pytest.mark.parametrize("secret_key", sorted(FORBIDDEN_SECRET_KEYS))
def test_rejects_forbidden_secret_keys_in_config(secret_key: str):
    with pytest.raises(MarketplaceValidationError) as exc:
        parse_asset_config(
            "connector_config",
            {
                "connector_type": "hubspot",
                "label": "HubSpot",
                secret_key: "leaked-value",
            },
        )
    assert any("forbidden_secret" in err for err in exc.value.errors)


@pytest.mark.parametrize(
    ("field_name", "payload"),
    [
        ("oauth_token", {"connector_type": "hubspot", "oauth_token": "x"}),
        ("nested bearer", {"connector_type": "hubspot", "metadata": {"bearer_token": "x"}}),
        ("suffix _secret", {"connector_type": "hubspot", "webhook_secret": "x"}),
        ("suffix _password", {"connector_type": "hubspot", "smtp_password": "x"}),
        ("suffix _api_key", {"connector_type": "hubspot", "stripe_api_key": "x"}),
        ("list item", {"connector_type": "hubspot", "headers": [{"authorization": "Bearer x"}]}),
    ],
)
def test_find_forbidden_secret_paths_cases(field_name: str, payload: dict):
    paths = find_forbidden_secret_paths(payload)
    assert paths, field_name


def test_allows_safe_config_fields():
    assert_no_forbidden_secrets(
        {
            "connector_type": "hubspot",
            "label": "HubSpot CRM",
            "connectPath": "/connectors?type=hubspot",
            "metadata": {"portal_id": "12345", "team_name": "Sales"},
        },
        field_label="config",
    )


def test_rejects_secret_fields_in_install_variables():
    with pytest.raises(MarketplaceValidationError) as exc:
        validate_asset_payload(
            asset_type="ai_agent",
            config={"name": "Agent", "purpose": "Test"},
            install_variables=[
                {
                    "key": "PORTAL",
                    "label": "Portal",
                    "default": "safe",
                    "metadata": {"api_key": "sk-live-leak"},
                }
            ],
        )
    assert any("install_variables" in err or "forbidden_secret" in err for err in exc.value.errors)


def test_rejects_secret_fields_in_required_connectors():
    with pytest.raises(MarketplaceValidationError) as exc:
        validate_asset_payload(
            asset_type="ai_agent",
            config={"name": "Agent", "purpose": "Test"},
            required_connectors=[
                {
                    "connectorType": "hubspot",
                    "label": "HubSpot",
                    "client_secret": "should-not-be-here",
                }
            ],
        )
    assert any("required_connectors" in err or "forbidden_secret" in err for err in exc.value.errors)


def test_rejects_nested_secret_in_department_pack_agent_config():
    with pytest.raises(MarketplaceValidationError) as exc:
        validate_asset_payload(
            asset_type="department_pack",
            config={
                "workflow_name": "Pack workflow",
                "agents": [
                    {
                        "name": "Agent",
                        "config": {"refresh_token": "oauth-leak"},
                    }
                ],
                "workflow_steps": _valid_workflow_config()["steps"],
            },
        )
    assert any("forbidden_secret" in err for err in exc.value.errors)


def test_assert_no_forbidden_secrets_reports_field_label():
    with pytest.raises(MarketplaceValidationError) as exc:
        assert_no_forbidden_secrets({"password": "x"}, field_label="install_variables")
    assert "install_variables must not contain secret" in exc.value.message
