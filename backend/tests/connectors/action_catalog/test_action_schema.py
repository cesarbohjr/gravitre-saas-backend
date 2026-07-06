"""Tests for catalog-wide action schema generation."""
from __future__ import annotations

from app.connectors.action_catalog.action_parameters import (
    ACTION_PARAMETERS,
    clear_action_schema_cache,
    parameters_for_action,
    resolve_action_schema,
)
from app.connectors.action_catalog.extensions import register_action_schema
from app.connectors.action_catalog.registry import all_catalog_action_specs
from app.connectors.action_catalog.schema_generator import infer_action_schema


def test_inferred_schema_has_no_generic_payload_blob():
    schema = infer_action_schema("salesforce.leads.create", kind="write")
    props = schema.get("properties", {})
    assert "payload" not in props
    assert "properties" in props


def test_list_action_has_query_and_limit():
    schema = parameters_for_action("zendesk.tickets.list", kind="read", suffix="tickets.list")
    props = schema["properties"]
    assert "limit" in props
    assert "connector_id" in props


def test_create_contact_requires_email_or_properties():
    schema = parameters_for_action("pipedrive.contacts.create", kind="write", suffix="contacts.create")
    assert "email" in schema["properties"] or "properties" in schema["properties"]


def test_manual_override_wins_over_inference():
    schema = resolve_action_schema("hubspot.contacts.search", kind="read", suffix="contacts.search")
    assert schema == ACTION_PARAMETERS["hubspot.contacts.search"]


def test_extension_override_wins():
    clear_action_schema_cache()
    register_action_schema(
        "custom.vendor.action",
        {"type": "object", "properties": {"custom_field": {"type": "string"}}, "required": ["custom_field"]},
    )
    schema = resolve_action_schema("custom.vendor.action", kind="read", suffix="action")
    assert "custom_field" in schema["properties"]


def test_all_catalog_actions_have_typed_schemas():
    payload_count = 0
    missing_connector_id = 0
    for spec in all_catalog_action_specs():
        schema = parameters_for_action(
            spec.id,
            kind=spec.kind,
            suffix=spec.id.split(".", 1)[-1],
        )
        props = schema.get("properties") or {}
        if "payload" in props and spec.id not in ACTION_PARAMETERS:
            payload_count += 1
        if "connector_id" not in props:
            missing_connector_id += 1
    assert payload_count == 0, f"{payload_count} actions still expose generic payload"
    assert missing_connector_id == 0


def test_catalog_api_includes_input_schema():
    from app.connectors.action_catalog.registry import list_full_catalog

    catalog = list_full_catalog()
    first_vendor = catalog["vendors"][0]
    first_action = first_vendor["tiers"]["v1"]["actions"][0]
    assert "inputSchema" in first_action
    assert first_action["inputSchema"].get("type") == "object"
