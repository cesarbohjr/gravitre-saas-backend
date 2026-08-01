"""All marketplace intelligence-pack workflows ship agents + instructions + actions."""
from __future__ import annotations

import pytest

from app.marketplace.intelligence_packs.catalog import list_intelligence_pack_specs
from app.marketplace.workflows.pack_workflows import (
    PACK_WORKFLOW_BUILDERS,
    assert_pack_workflow_preconfigured,
)
from app.marketplace.workflow_contract import steps_to_rich_contract
from app.services.tool_service import list_registered_actions
from app.workflows.constants import SCHEMA_VERSION
from app.workflows.schema import validate_definition


def test_every_catalog_pack_has_workflow_builder():
    specs = list_intelligence_pack_specs()
    assert len(specs) == 12
    for spec in specs:
        assert spec.pack_id in PACK_WORKFLOW_BUILDERS, spec.pack_id
        assert spec.workflow_steps, spec.pack_id
        assert_pack_workflow_preconfigured(list(spec.workflow_steps))


@pytest.mark.parametrize("pack_id", sorted(PACK_WORKFLOW_BUILDERS))
def test_pack_builder_matches_catalog_and_validates(pack_id: str):
    from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec

    builder = PACK_WORKFLOW_BUILDERS[pack_id]
    built = builder()
    assert_pack_workflow_preconfigured(built)
    spec = get_intelligence_pack_spec(pack_id)
    assert spec is not None
    assert len(spec.workflow_steps) == len(built)
    validate_definition({"schema_version": SCHEMA_VERSION, "steps": built})
    nodes, edges = steps_to_rich_contract(built)
    assert len(nodes) == len(built)
    assert len(edges) == max(0, len(built) - 1)
    agent_nodes = [n for n in nodes if n.get("type") == "agent"]
    assert agent_nodes
    assert all(
        len(str((n.get("metadata") or {}).get("task") or n.get("description") or "")) >= 40
        for n in agent_nodes
    )


@pytest.mark.parametrize("pack_id", sorted(PACK_WORKFLOW_BUILDERS))
def test_pack_tool_actions_are_registered(pack_id: str):
    registered = set(list_registered_actions())
    steps = PACK_WORKFLOW_BUILDERS[pack_id]()
    for step in steps:
        if step.get("type") != "invoke_tool":
            continue
        action = str((step.get("config") or {}).get("action") or "")
        assert action in registered, f"{pack_id}: {action}"
        assert (step.get("config") or {}).get("selectedAction") or "." in action


def test_department_pack_workflows_are_preconfigured():
    from app.marketplace.seed_catalog import list_catalog_assets

    for asset in list_catalog_assets():
        if asset.asset_type != "department_pack":
            continue
        steps = list((asset.config or {}).get("workflow_steps") or [])
        assert_pack_workflow_preconfigured(steps)
