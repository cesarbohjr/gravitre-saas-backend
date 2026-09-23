"""2.0-H task continuity — one plan_id frame, CS-7 that/last-one, restart vs follow-up."""
from __future__ import annotations

from app.services.analytics_traffic_overview_service import detect_analytics_traffic_intent
from app.services.compiled_task_service import project_compiled_task
from app.services.execution_plan_adapters import enrich_task_state_patch
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep, reconcile_execution_plan
from app.services.reference_resolver import resolve_reference
from app.services.task_continuity import (
    active_task_frame,
    decide_task_continuity,
    is_continuity_followup,
    is_restart_utterance,
    pending_family,
)


def _traffic_state(*, terminal: str = "completed") -> dict:
    plan = ExecutionPlan(
        plan_id="plan-traffic-1",
        summary="Website traffic last month",
        objective="Tell me what my website traffic was last month.",
        capability_id="analytics.traffic_overview",
        source="test",
        terminal_status=terminal,  # type: ignore[arg-type]
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
    compiled = project_compiled_task(
        {
            "execution_plan": plan.as_dict(),
            "cognitive_resolution_message": "Tell me what my website traffic was last month.",
            "active_analysis": {
                "kind": "analytics.traffic_overview",
                "connector_id": "google_analytics",
                "property_id": "123",
                "property_name": "gravitre.app",
            },
        }
    ).as_dict()
    return {
        "execution_plan": plan.as_dict(),
        "compiled_task": compiled,
        "active_analysis": {
            "kind": "analytics.traffic_overview",
            "connector_id": "google_analytics",
            "property_id": "123",
            "property_name": "gravitre.app",
        },
        "cognitive_resolution_message": "Tell me what my website traffic was last month.",
    }


def test_that_resolves_from_compiled_task_without_active_analysis() -> None:
    state = {
        "compiled_task": {
            "plan_id": "plan-traffic-1",
            "capability_id": "analytics.traffic_overview",
            "objective_text": "website traffic last month",
            "sources": [{"connector": "google_analytics", "resource_id": "123"}],
        }
    }
    ref = resolve_reference("break that down by channel", state)
    assert ref.matched is True
    assert ref.kind == "referent"
    assert ref.referent["plan_id"] == "plan-traffic-1"


def test_follow_up_keeps_same_plan_id_and_updates_compiled_task() -> None:
    state = _traffic_state()
    continued = reconcile_execution_plan(
        message="what about last week?",
        task_state=state,
        turn_id="turn-2",
    )
    assert continued.plan_id == "plan-traffic-1"
    assert continued.continuation_of_plan_id == "plan-traffic-1"
    assert continued.replan_reason == "follow_up"
    assert continued.revision == 2
    patch = enrich_task_state_patch(
        {"execution_plan": continued.as_dict(), "cognitive_resolution_message": "what about last week?"},
        current_state=state,
    )
    assert patch["compiled_task"]["plan_id"] == "plan-traffic-1"
    assert patch["compiled_task"]["capability_id"] == "analytics.traffic_overview"
    window = patch["compiled_task"].get("timeframe_resolved") or {}
    assert "week" in str(window.get("interpretation") or "").lower() or "last week" in (
        patch["compiled_task"].get("objective_text") or ""
    ).lower()


def test_last_one_selects_option() -> None:
    state = {
        **_traffic_state(),
        "previous_option_set": [
            {"id": "a", "label": "Sessions"},
            {"id": "b", "label": "Channels"},
        ],
    }
    ref = resolve_reference("the last one", state)
    assert ref.matched is True
    assert ref.selected_indices == (1,)


def test_restart_intent_mints_new_plan() -> None:
    state = _traffic_state()
    assert is_restart_utterance("forget that, who owes us money", state) is True
    assert decide_task_continuity("forget that, who owes us money", state) == "restart"
    next_plan = reconcile_execution_plan(
        message="forget that, who owes us money",
        task_state=state,
        connected_integrations=["quickbooks"],
    )
    assert next_plan.plan_id != "plan-traffic-1"


def test_analytics_follow_up_still_routes_to_traffic_handler() -> None:
    state = _traffic_state()
    intent = detect_analytics_traffic_intent(
        "break that down by channel",
        task_state=state,
        connected_integrations=["google_analytics"],
    )
    assert intent is not None
    assert intent.is_followup is True
    assert is_continuity_followup("break that down by channel", state) is True


def test_pending_family_is_projection_not_new_runtime() -> None:
    state = {
        "pending_task": {"status": "awaiting_confirm", "execution_plan_id": "plan-traffic-1"},
        "pending_action": {"status": "awaiting_user", "plan_id": "plan-traffic-1"},
        "offered_action": {"status": "awaiting_user_confirmation", "execution_plan_id": "plan-traffic-1"},
        "execution_plan": _traffic_state(terminal="waiting_for_approval")["execution_plan"],
    }
    family = pending_family(state)
    assert set(family) == {"pending_task", "pending_action", "offered_action"}
    frame = active_task_frame(state)
    assert frame is not None
    assert frame["plan_id"] == "plan-traffic-1"
    continued = reconcile_execution_plan(message="yes", task_state=state)
    assert continued.plan_id == "plan-traffic-1"
    assert continued.terminal_status == "running"


def test_pipeline_analysis_follow_up_continues_completed_frame() -> None:
    state = {
        "execution_plan": {
            "plan_id": "plan-pipe-1",
            "capability_id": "sales.pipeline.health",
            "terminal_status": "completed",
            "steps": [],
        },
        "provider_result_evidence": {
            "action_key": "hubspot.deals.list",
            "provider_invoked": True,
            "result_count": 25,
        },
    }
    assert decide_task_continuity("What appears important?", state) == "continue"
    assert decide_task_continuity("What is missing?", state) == "continue"
