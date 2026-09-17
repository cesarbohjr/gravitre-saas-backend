"""compiled_task projection on task_state (audit §34 item 4)."""
from __future__ import annotations

from app.services.canonical_cognitive_resolution import apply_canonical_cognitive_resolution
from app.services.cognitive_trace_engine import CognitiveTurnTrace, sync_trace_from_task_state
from app.services.compiled_task_service import project_compiled_task
from app.services.execution_plan_adapters import enrich_task_state_patch
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from unittest.mock import patch

import pytest


def test_project_includes_timeframe_and_source() -> None:
    compiled = project_compiled_task(
        {
            "cognitive_resolution_message": "Tell me what my website traffic was last month.",
            "resolution_trace": {
                "turn_id": "turn-1",
                "tenant_id": "org-1",
                "resolved_connector_id": "google_analytics",
                "resource_id": "123",
                "clarification_required": False,
            },
            "timezone": "America/Los_Angeles",
        }
    )
    payload = compiled.as_dict()
    assert payload["objective_text"].startswith("Tell me what my website traffic")
    assert payload["timeframe_resolved"] is not None
    assert payload["timeframe_resolved"]["interpretation"] == "previous_calendar_month"
    assert payload["sources"][0]["connector"] == "google_analytics"
    assert payload["sources"][0]["resource_id"] == "123"
    assert payload["clarification_decision"]["required"] is False
    assert payload["turn_id"] == "turn-1"


def test_preflight_parameters_are_sanitized() -> None:
    compiled = project_compiled_task(
        {},
        preflight={
            "status": "ready",
            "action_key": "google_analytics.reports.run",
            "capability_id": "analytics.traffic_overview",
            "compiled_parameters": {
                "property_id": "123",
                "start_date": "2026-08-01",
                "api_token": "secret",
            },
        },
    )
    assert compiled.preflight_status == "ready"
    assert compiled.compiled_parameters["property_id"] == "123"
    assert "api_token" not in compiled.compiled_parameters
    assert compiled.capability_id == "analytics.traffic_overview"


def test_enrich_patch_reprojects_compiled_task() -> None:
    plan = ExecutionPlan(
        plan_id="plan-1",
        summary="Traffic",
        objective="Tell me last month traffic",
        capability_id="analytics.traffic_overview",
        source="test",
        steps=[
            ExecutionStep(
                step_id="s1",
                title="GA4 report",
                kind="read",
                connector_id="google_analytics",
                action_key="google_analytics.reports.run",
            )
        ],
    )
    patch = enrich_task_state_patch(
        {"execution_plan": plan.as_dict()},
        current_state={"cognitive_resolution_message": "Tell me last month traffic"},
    )
    assert patch["compiled_task"]["capability_id"] == "analytics.traffic_overview"
    assert "google_analytics.reports.run" in patch["compiled_task"]["action_keys"]


def test_sync_trace_links_compiled_task() -> None:
    trace = CognitiveTurnTrace(turn_id="t1")
    sync_trace_from_task_state(
        trace,
        {
            "compiled_task": {
                "turn_id": "t1",
                "capability_id": "analytics.traffic_overview",
                "preflight_status": "ready",
            }
        },
    )
    assert trace.linked["compiled_task"] == "t1"
    assert trace.linked["compiled_task_capability"] == "analytics.traffic_overview"
    assert trace.linked["compiled_task_preflight"] == "ready"


@pytest.mark.asyncio
async def test_phase_a_ingress_writes_compiled_task() -> None:
    with patch(
        "app.services.cognitive_resolution_pipeline.resolve_resource_request",
    ):
        result, merged = await apply_canonical_cognitive_resolution(
            message="hello",
            task_state={},
            tenant_id="org-1",
            user_id="user-1",
            client=object(),
            connected_integrations=["google_analytics"],
        )
    assert result is not None
    compiled = merged.get("compiled_task")
    assert isinstance(compiled, dict)
    assert compiled["objective_text"] == "hello"
    assert compiled["org_id"] == "org-1"
