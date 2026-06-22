from __future__ import annotations

import pytest

from app.services.plan_resolution_service import (
    PlanResolutionMode,
    PlanResolutionRequest,
    resolve_plan,
)


def test_resolve_plan_runtime_default():
    resolved = resolve_plan(
        PlanResolutionRequest(
            surface="operator",
            task_text="Analyze sync failures",
            agent={"id": "agent-1", "name": "Ops"},
        )
    )
    assert resolved.mode == PlanResolutionMode.GENERATE_AT_RUNTIME
    assert resolved.task_text == "Analyze sync failures"
    assert resolved.metadata["planSource"] == "runtime"


def test_resolve_plan_swarm_subtask():
    resolved = resolve_plan(
        PlanResolutionRequest(
            surface="swarm",
            task_text="ignored",
            agent={"id": "agent-2", "name": "Analyst"},
            subtask_spec={
                "task": "Review connector latency",
                "objective": "Reduce downtime",
                "scopedTools": [{"name": "connector_status"}],
                "subtaskId": "sub-1",
            },
        )
    )
    assert resolved.mode == PlanResolutionMode.RESOLVE_EXISTING
    assert "Reduce downtime" in resolved.task_text
    assert "Review connector latency" in resolved.task_text
    assert resolved.permitted_tools == ["connector_status"]
    assert resolved.metadata["planSource"] == "swarm_subtask"


def test_resolve_plan_swarm_subtask_connector_type():
    resolved = resolve_plan(
        PlanResolutionRequest(
            surface="swarm",
            task_text="ignored",
            agent={"id": "agent-2", "name": "Analyst"},
            subtask_spec={
                "task": "Search CRM contacts",
                "scopedTools": [{"connectorType": "hubspot", "action": "search_contacts"}],
            },
        )
    )
    assert resolved.permitted_tools == ["hubspot"]


def test_resolve_plan_workflow_step():
    resolved = resolve_plan(
        PlanResolutionRequest(
            surface="workflow",
            task_text="fallback",
            agent={"id": "agent-3"},
            existing_plan={
                "task": "Send follow-up email",
                "step_id": "step-email",
                "step_type": "agent",
                "permittedTools": ["email_send"],
            },
            step_outputs={"step-1": {"summary": "Lead scored"}},
        )
    )
    assert resolved.mode == PlanResolutionMode.RESOLVE_EXISTING
    assert resolved.task_text == "Send follow-up email"
    assert resolved.permitted_tools == ["email_send"]
    assert resolved.upstream_context == {"step_outputs": {"step-1": {"summary": "Lead scored"}}}
