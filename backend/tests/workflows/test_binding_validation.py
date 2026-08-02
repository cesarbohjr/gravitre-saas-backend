"""Design-time binding validation — named codes, MSP golden path."""
from __future__ import annotations

import copy

import pytest

from app.marketplace.workflows.msp_enrichment_workflow import (
    INSTALL_VARIABLES,
    build_msp_enrichment_workflow_steps,
)
from app.workflows.binding_validation import (
    assert_bindings_valid,
    validate_bindings,
)
from app.workflows.constants import SCHEMA_VERSION
from app.workflows.schema import WorkflowValidationError


def _msp_definition() -> dict:
    return {"schema_version": SCHEMA_VERSION, "steps": build_msp_enrichment_workflow_steps()}


def _declared() -> set[str]:
    return {str(row["key"]) for row in INSTALL_VARIABLES}


def test_msp_enrichment_bindings_pass():
    result = validate_bindings(_msp_definition(), declared_parameters=_declared())
    assert result.ok, [e.as_dict() for e in result.errors]


def test_unknown_from_step_fails():
    definition = _msp_definition()
    for step in definition["steps"]:
        if step["id"] == "clay_push":
            step["config"]["param_sources"]["records"] = {
                "from_step": "does_not_exist",
                "path": ["records"],
            }
    result = validate_bindings(definition, declared_parameters=_declared())
    assert not result.ok
    assert any(e.code == "binding.from_step_unknown" for e in result.errors)


def test_from_step_not_upstream_fails():
    definition = _msp_definition()
    for step in definition["steps"]:
        if step["id"] == "apollo_lists":
            step["config"] = {
                "action": "apollo.lists.list",
                "param_sources": {
                    "records": {"from_step": "clay_push", "path": ["records"]},
                },
            }
    result = validate_bindings(definition, declared_parameters=_declared())
    assert any(e.code == "binding.from_step_not_upstream" for e in result.errors)


def test_path_unknown_fails():
    definition = _msp_definition()
    for step in definition["steps"]:
        if step["id"] == "clay_push":
            step["config"]["param_sources"]["records"] = {
                "from_step": "apollo_contacts_search",
                "path": ["not_a_real_output"],
            }
    result = validate_bindings(definition, declared_parameters=_declared())
    assert any(e.code == "binding.path_unknown" for e in result.errors)


def test_path_empty_fails():
    definition = _msp_definition()
    for step in definition["steps"]:
        if step["id"] == "clay_push":
            step["config"]["param_sources"]["records"] = {
                "from_step": "apollo_contacts_search",
                "path": [],
            }
    result = validate_bindings(definition, declared_parameters=_declared())
    assert any(e.code == "binding.path_empty" for e in result.errors)


def test_dollar_unresolved_fails():
    definition = _msp_definition()
    for step in definition["steps"]:
        if step["id"] == "hubspot_crm_sync":
            step["config"]["param_sources"]["crm_connector_id"] = "$totally_unknown_param"
    result = validate_bindings(definition, declared_parameters=_declared())
    assert any(e.code == "binding.dollar_unresolved" for e in result.errors)


def test_hubspot_connector_id_runtime_alias_allowed():
    definition = _msp_definition()
    # Only install vars declared — hubspot_connector_id is a known runtime alias.
    result = validate_bindings(definition, declared_parameters={"HUBSPOT_LIST_ID"})
    assert result.ok, [e.as_dict() for e in result.errors]


def test_action_unknown_fails():
    definition = _msp_definition()
    for step in definition["steps"]:
        if step["id"] == "clay_push":
            step["config"]["action"] = "clay.not.a.real.action"
    result = validate_bindings(definition, declared_parameters=_declared())
    assert any(e.code == "binding.action_unknown" for e in result.errors)


def test_assert_bindings_valid_raises_named_codes():
    definition = _msp_definition()
    broken = copy.deepcopy(definition)
    for step in broken["steps"]:
        if step["id"] == "hubspot_crm_sync":
            step["config"]["param_sources"]["records"] = {
                "from_step": "missing_step",
                "path": ["records"],
            }
    with pytest.raises(WorkflowValidationError) as exc:
        assert_bindings_valid(broken, declared_parameters=_declared())
    assert "binding.from_step_unknown" in (exc.value.errors or [])
