from __future__ import annotations

import uuid

from app.services.marketo_workflow_service import (
    abm_handoff_workflow_id,
    build_abm_handoff_workflow_definition,
    build_webinar_followup_workflow_definition,
    webinar_followup_workflow_id,
)


def test_abm_handoff_workflow_id_stable():
    org = str(uuid.uuid4())
    assert abm_handoff_workflow_id(org) == abm_handoff_workflow_id(org)


def test_build_abm_handoff_includes_handoff_and_marketo_steps():
    org = str(uuid.uuid4())
    definition = build_abm_handoff_workflow_definition(org_id=org, marketo_connector_id="mk-1")
    step_types = [s["type"] for s in definition["steps"]]
    assert "agent" in step_types
    assert "invoke_tool" in step_types
    sales_step = definition["steps"][0]
    assert sales_step["metadata"].get("next_agent_id")
    marketo_actions = [
        s["config"]["action"]
        for s in definition["steps"]
        if s.get("type") == "invoke_tool"
    ]
    assert "marketo.leads.update" in marketo_actions
    assert "marketo.lists.add_to_static_list" in marketo_actions


def test_build_webinar_followup_uses_handoff_bus():
    org = str(uuid.uuid4())
    definition = build_webinar_followup_workflow_definition(org_id=org, marketo_connector_id="mk-1")
    assert webinar_followup_workflow_id(org) == webinar_followup_workflow_id(org)
    intake = definition["steps"][0]
    assert intake["metadata"].get("briefing_from_steps") is True
    tool_steps = [s for s in definition["steps"] if s.get("type") == "invoke_tool"]
    assert any(s["config"]["action"] == "marketo.programs.status" for s in tool_steps)
