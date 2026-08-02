"""MSP Prospecting & List Builder workflow definition tests."""
from __future__ import annotations

from app.marketplace.workflows.msp_prospecting_list_workflow import (
    SCOUT_AGENT_SLUG,
    WORKFLOW_NAME,
    build_msp_prospecting_list_workflow_steps,
)
from app.services.tool_service import list_registered_actions
from app.workflows.schema import validate_definition
from app.workflows.constants import SCHEMA_VERSION


def test_msp_prospecting_list_workflow_steps_validate():
    steps = build_msp_prospecting_list_workflow_steps()
    assert len(steps) >= 8
    types = {s["type"] for s in steps}
    assert "agent" in types
    assert "invoke_tool" in types
    assert sum(1 for s in steps if s["type"] == "agent") == 3
    assert sum(1 for s in steps if s["type"] == "invoke_tool") == 7
    validate_definition({"schema_version": SCHEMA_VERSION, "steps": steps})


def test_msp_prospecting_membership_is_deterministic():
    steps = build_msp_prospecting_list_workflow_steps()
    actions = [
        s["config"]["action"] for s in steps if s.get("type") == "invoke_tool"
    ]
    assert "apollo.lists.create" in actions
    assert "apollo.lists.add" in actions
    assert "hubspot.lists.create" in actions
    assert "hubspot.contacts.create" in actions
    assert "hubspot.lists.add_contact" in actions
    add = next(s for s in steps if s.get("id") == "apollo_list_add")
    assert add["config"]["param_sources"]["entity_ids"]["from_step"] == "apollo_people_search"


def test_msp_prospecting_list_workflow_tool_actions_registered():
    registered = set(list_registered_actions())
    steps = build_msp_prospecting_list_workflow_steps()
    for step in steps:
        if step["type"] != "invoke_tool":
            continue
        action = step["config"]["action"]
        assert action in registered, action


def test_msp_prospecting_list_workflow_agent_seeds():
    steps = build_msp_prospecting_list_workflow_steps()
    agent_steps = [s for s in steps if s["type"] == "agent"]
    assert all(
        (s.get("metadata") or {}).get("agent_seed") == f"agent:{SCOUT_AGENT_SLUG}"
        for s in agent_steps
    )
    assert all((s.get("metadata") or {}).get("assignment") is True for s in agent_steps)
    assert "Prospecting" in WORKFLOW_NAME or "List" in WORKFLOW_NAME
