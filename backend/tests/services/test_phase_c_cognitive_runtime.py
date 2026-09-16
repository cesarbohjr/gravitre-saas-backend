"""Phase C — execution plan SoT, parallel reads, replanner, terminal policy."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.cognitive_execution_engine import execute_read_steps_parallel
from app.services.cognitive_execution_replanner import (
    build_cross_source_analytics_plan,
    replan_budget_remaining,
    should_replan,
)
from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionPlan,
    ExecutionStep,
    reconcile_execution_plan,
)
from app.services.terminal_turn_policy import enforce_terminal_turn_outcome


def test_reconcile_prefers_pending_task() -> None:
    plan = reconcile_execution_plan(
        message="yes",
        task_state={
            "pending_task": {
                "status": "awaiting_confirm",
                "action": "hubspot.contacts.create",
                "connector_id": "hubspot",
            }
        },
    )
    assert plan.source in {"pending_task", "pending_task_bridge"}
    assert plan.steps[0].connector_id == "hubspot"


def test_cross_source_plan_when_ga4_and_gsc_connected() -> None:
    plan = build_cross_source_analytics_plan(
        "How is my website doing?",
        capability_id="analytics.traffic_overview",
        connected_integrations=["google_analytics", "google_search_console"],
    )
    assert plan is not None
    assert len(plan.steps) == 3
    assert {s.connector_id for s in plan.steps if s.kind == "read"} == {
        "google_analytics",
        "google_search_console",
    }


def test_replan_budget_and_should_replan() -> None:
    plan = ExecutionPlan(
        plan_id="p1",
        summary="test",
        steps=[
            ExecutionStep(
                step_id="read_ga4",
                title="GA4",
                kind="read",
                connector_id="google_analytics",
                status="failed",
            )
        ],
        source="test",
        replan_budget=1,
    )
    assert replan_budget_remaining(plan) == 1
    assert should_replan(plan, partial_failure=True) is True


@pytest.mark.asyncio
async def test_parallel_read_execution() -> None:
    plan = ExecutionPlan(
        plan_id="p1",
        summary="parallel",
        steps=[
            ExecutionStep(step_id="a", title="A", kind="read", connector_id="google_analytics"),
            ExecutionStep(step_id="b", title="B", kind="read", connector_id="google_search_console"),
        ],
        source="test",
    )

    async def handler(step: ExecutionStep, _ctx: dict) -> ExecutionObservation:
        return ExecutionObservation(
            step_id=step.step_id,
            connector_id=str(step.connector_id),
            success=True,
            summary=f"ok-{step.step_id}",
        )

    observations = await execute_read_steps_parallel(plan, context={}, handler=handler)
    assert len(observations) == 2
    assert all(o.success for o in observations)


def test_terminal_policy_blocks_defer_without_pending() -> None:
    out = enforce_terminal_turn_outcome(
        "I'll check your GA4 traffic and get back to you.",
        task_state={},
        workflow_status="in_progress",
    )
    assert "I'll check" not in out
    assert "Connectors" in out


def test_terminal_policy_allows_defer_with_offered_action() -> None:
    msg = "I'll check your connectors now."
    out = enforce_terminal_turn_outcome(
        msg,
        task_state={"offered_action": {"status": "awaiting_user_confirmation"}},
        workflow_status="pending",
    )
    assert out == msg


@pytest.mark.asyncio
async def test_cross_source_analytics_turn_mocked() -> None:
    from app.services.analytics_traffic_overview_service import try_analytics_traffic_overview_turn

    ga4_obs = ExecutionObservation(
        step_id="read_ga4_traffic",
        connector_id="google_analytics",
        success=True,
        summary="GA4 ok",
        structured={"active_users": 100, "sessions": 200},
    )
    gsc_obs = ExecutionObservation(
        step_id="read_gsc_performance",
        connector_id="google_search_console",
        success=True,
        summary="GSC ok",
        structured={"top_page": "/home", "top_clicks": 50},
    )

    with patch(
        "app.services.cognitive_execution_engine.execute_read_steps_parallel",
        new_callable=AsyncMock,
        return_value=[ga4_obs, gsc_obs],
    ), patch(
        "app.services.cognitive_execution_replanner.build_cross_source_analytics_plan",
        return_value=ExecutionPlan(
            plan_id="x",
            summary="cross",
            steps=[
                ExecutionStep(step_id="read_ga4_traffic", title="GA4", kind="read", connector_id="google_analytics"),
                ExecutionStep(step_id="read_gsc_performance", title="GSC", kind="read", connector_id="google_search_console"),
            ],
            source="test",
        ),
    ):
        turn = await try_analytics_traffic_overview_turn(
            message="How is my website doing?",
            org_id="org-1",
            client=object(),
            connected_integrations=["google_analytics", "google_search_console"],
            task_state={},
        )
    assert turn is not None
    assert turn.get("stop_pipeline") is True
    assert "cross-source" in str(turn.get("message") or "").lower()
