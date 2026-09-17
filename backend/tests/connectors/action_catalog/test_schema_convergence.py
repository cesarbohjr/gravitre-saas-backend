"""JSON Schema, workflow schema, and advertised executor contract share one ActionSpec."""
from __future__ import annotations

from app.connectors.action_catalog.action_parameters import resolve_action_schema
from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema, iter_workflow_fields
from app.connectors.action_catalog.canonical_action_schema import (
    HUBSPOT_SEARCH_ACTIONS,
    user_facing_required,
)
from app.connectors.action_catalog.f1_read_slice import F1_CATALOG_ACTIONS, registry_action_key
from app.connectors.action_catalog.registry import get_action_spec
from app.services.tool_service import _resolve_hubspot_search


def _json_required(action_key: str, spec) -> list[str]:
    schema = resolve_action_schema(
        action_key,
        kind=spec.kind,
        suffix=spec.id.split(".", 1)[-1],
        description=spec.description,
        explicit_schema=spec.input_schema,
    )
    return list(schema.get("required") or [])


def _workflow_required(action_key: str) -> set[str]:
    schema = get_workflow_schema(action_key)
    assert schema is not None, action_key
    keys: set[str] = set()
    for field in schema.required_fields or ():
        keys.update(field.arg_keys)
    return keys


def _converged_keys() -> list[str]:
    return sorted(set(F1_CATALOG_ACTIONS) | set(HUBSPOT_SEARCH_ACTIONS))


def test_f1_and_hubspot_search_share_one_user_facing_required_set():
    for catalog_key in _converged_keys():
        spec = get_action_spec(catalog_key)
        assert spec is not None, catalog_key
        expected = set(user_facing_required(spec))
        json_req = set(_json_required(catalog_key, spec))
        wf_req = _workflow_required(catalog_key)
        assert json_req == expected, catalog_key
        assert wf_req == expected, catalog_key
        alias = registry_action_key(catalog_key)
        if alias != catalog_key:
            assert set(_json_required(alias, spec)) == expected
            assert _workflow_required(alias) == expected


def test_ga4_api_required_stays_on_spec_not_user_facing_required():
    spec = get_action_spec("google_analytics.reports.run")
    assert spec is not None
    assert "property_id" in spec.required_parameters
    assert "property_id" not in user_facing_required(spec)
    assert "property_id" not in _json_required("analytics.reports.run", spec)
    assert "property_id" not in _workflow_required("analytics.reports.run")


def test_hubspot_search_executor_accepts_the_advertised_empty_required_contract():
    for action in sorted(HUBSPOT_SEARCH_ACTIONS):
        spec = get_action_spec(action)
        assert spec is not None
        assert _json_required(action, spec) == []
        assert _workflow_required(action) == set()
        object_name = action.split(".")[1]
        assert _resolve_hubspot_search(object_name, {}) is None
        assert _resolve_hubspot_search(object_name, {"query": "acme"})


def test_stamped_action_spec_is_the_schema_source():
    spec = get_action_spec("hubspot.deals.search")
    assert spec is not None
    assert spec.input_schema is not None
    assert spec.workflow_schema is not None
    json_props = set((spec.input_schema.get("properties") or {}).keys())
    wf_keys: set[str] = set()
    for field in iter_workflow_fields(spec.workflow_schema):
        wf_keys.update(field.arg_keys)
    assert "query" in json_props
    assert "query" in wf_keys
    assert "filter_groups" in json_props
    assert "filter_groups" in wf_keys
