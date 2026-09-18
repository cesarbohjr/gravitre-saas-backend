"""Single ActionSpec-owned schema for JSON, workflow, and advertised executor contract.

F1 overlays and the HubSpot search class stamp `input_schema` + `workflow_schema`
at catalog construction. ReAct (`resolve_action_schema`) and the chat gate
(`get_workflow_schema`) both read those fields. API-required parameters that
preflight/resolvers can fill stay off user-facing `required` lists.

Do not import this module from executors. Do not expand the F1 action set here.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.connectors.action_catalog.models import ActionSpec, ActionWorkflowSchema, WorkflowFieldSpec
from app.connectors.action_catalog.schema_generator import normalize_schema

# Sources that compile without asking the user — not JSON/workflow required.
_COMPILE_SOURCES = frozenset(
    {
        "REFERENCE_STATE",
        "TASK_CONTEXT",
        "BUSINESS_IDENTITY",
        "RESOURCE_RESOLVER",
        "CONNECTOR_METADATA",
        "TIME_RESOLVER",
        "CAPABILITY_RECIPE",
        "ACTION_DEFAULT",
        "PREVIOUS_OBSERVATION",
    }
)

HUBSPOT_SEARCH_ACTIONS: frozenset[str] = frozenset(
    {
        "hubspot.deals.search",
        "hubspot.contacts.search",
        "hubspot.companies.search",
        "hubspot.tickets.search",
    }
)


def _rule_map(spec: ActionSpec) -> dict[str, Any]:
    return {rule.parameter: rule for rule in spec.parameter_source_rules}


def user_facing_required(spec: ActionSpec) -> tuple[str, ...]:
    """Keys the model/chat gate must supply. API-required compile fields are omitted."""
    rules = _rule_map(spec)
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)

    for rule in spec.parameter_source_rules:
        if rule.required_from_user:
            _add(rule.parameter)
    for name in spec.required_parameters:
        rule = rules.get(name)
        if rule and rule.required_from_user:
            _add(name)
            continue
        if rule and any(source in _COMPILE_SOURCES for source in rule.sources):
            continue
        if rule and rule.required_by_api:
            _add(name)
            continue
        if not rule:
            _add(name)
    return tuple(ordered)


def advertised_property_names(spec: ActionSpec) -> tuple[str, ...]:
    """LLM/workflow fields: catalog JSON properties plus user-visible params.

    Compile-only resources (portal_id, realm_id, …) stay on source rules, not
    the advertised schema, unless they are already in ACTION_PARAMETERS.
    """
    names: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    override = _lookup_parameter_override(spec.id) or {}
    for name in (override.get("properties") or {}):
        _add(str(name))
    for name in (spec.input_schema or {}).get("properties") or {}:
        _add(str(name))
    for name in user_facing_required(spec):
        _add(name)
    for name in spec.optional_parameters:
        _add(name)
    return tuple(names)


def _lookup_parameter_override(action_id: str) -> dict[str, Any] | None:
    from app.connectors.action_catalog.action_parameters import ACTION_PARAMETERS
    from app.connectors.action_catalog.f1_read_slice import registry_action_key

    for key in (action_id, registry_action_key(action_id)):
        raw = ACTION_PARAMETERS.get(key)
        if raw:
            return dict(raw)
    return None


def json_schema_for_spec(spec: ActionSpec) -> dict[str, Any]:
    from app.connectors.action_catalog.schema_generator import infer_action_schema

    base = (
        spec.input_schema
        or _lookup_parameter_override(spec.id)
        or infer_action_schema(spec.id, kind=spec.kind, description=spec.description or spec.id)
    )
    schema = normalize_schema(dict(base))
    properties = dict(schema.get("properties") or {})
    for name in advertised_property_names(spec):
        if name not in properties:
            properties[name] = {"type": "string", "description": name.replace("_", " ")}
    rules = _rule_map(spec)
    for name in list(properties):
        rule = rules.get(name)
        if rule and rule.default is not None and "default" not in properties[name]:
            properties[name] = {**properties[name], "default": rule.default}
    schema["properties"] = properties
    schema["required"] = list(user_facing_required(spec))
    return normalize_schema(schema)


def workflow_schema_for_spec(spec: ActionSpec) -> ActionWorkflowSchema:
    required = tuple(
        WorkflowFieldSpec(name.replace("_", " "), (name,), inferrable=True)
        for name in user_facing_required(spec)
    )
    required_set = set(user_facing_required(spec))
    optional_names = [
        name
        for name in advertised_property_names(spec)
        if name not in required_set and name != "connector_id"
    ]
    optional = tuple(
        WorkflowFieldSpec(name.replace("_", " "), (name,), inferrable=True) for name in optional_names
    )
    return ActionWorkflowSchema(
        intent_label=spec.name or spec.id,
        required_fields=required,
        optional_fields=optional,
    )


def should_stamp_canonical_schema(spec: ActionSpec) -> bool:
    from app.connectors.action_catalog.f1_read_slice import is_f1_read_action
    from app.connectors.action_catalog.f1_write_slice import is_f1_write_action

    return is_f1_read_action(spec.id) or is_f1_write_action(spec.id) or spec.id in HUBSPOT_SEARCH_ACTIONS


def stamp_canonical_schemas(spec: ActionSpec) -> ActionSpec:
    """Fill empty input/workflow schemas from the ActionSpec contract."""
    if not should_stamp_canonical_schema(spec):
        return spec
    updates: dict[str, Any] = {}
    working = spec
    if not spec.input_schema:
        updates["input_schema"] = json_schema_for_spec(spec)
        working = replace(spec, **updates)
    else:
        # Keep catalog properties; force required[] to match user-facing rules.
        schema = normalize_schema(dict(spec.input_schema))
        schema["required"] = list(user_facing_required(spec))
        working = replace(spec, input_schema=schema)
    if not working.workflow_schema:
        working = replace(working, workflow_schema=workflow_schema_for_spec(working))
    return working
