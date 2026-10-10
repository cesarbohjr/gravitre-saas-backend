"""Sealed reads label observations with the vendor, not the connection row id.

A live "how's my website doing" answer showed raw ids instead of the numbers:
invoke_tool returned the connection's UUID as connector_id, so the cross-source
answer found no Analytics or Search observation and the blocks were titled
with the UUID.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.analytics_traffic_overview_service import (
    _compose_cross_source_message,
)
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.sealed_read_execution import invoke_sealed_f1_read
from app.services.structured_assistant_response import (
    blocks_from_execution_observations,
)
from app.services.tool_types import NormalizedResult, ToolContext

CONNECTION_ID = "c283f76a-deed-41d0-9f2d-2b98e9f95dd9"


def _proof() -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        compiled_parameters={"property_id": "123", "start_date": "2026-09-28", "end_date": "2026-10-04"},
        time_window={"interpretation": "last_week"},
        connector_id="google_analytics",
        capability_id="analytics.traffic_overview",
        resource={"id": "123"},
    )


def test_observation_uses_vendor_and_answer_shows_the_numbers() -> None:
    step = ExecutionStep(
        step_id="s1", title="traffic", kind="evidence", connector_id="google_analytics",
        action_key="google_analytics.reports.run",
    )
    plan = ExecutionPlan(plan_id="p1", summary="traffic", steps=[step], source="sealed_read")
    ctx = ToolContext(settings=None, client=None, org_id="org", actor_id="u", environment_name="production")
    invoked = NormalizedResult(
        success=True, action="google_analytics.reports.run", connector_id=CONNECTION_ID, data={"rows": []}
    )
    with (
        patch("app.services.sealed_read_execution.preflight_read_action", return_value=_proof()),
        patch("app.services.sealed_read_execution.invoke_tool", return_value=invoked),
    ):
        _inv, _proof_out, obs = invoke_sealed_f1_read(
            ctx=ctx,
            action_key="google_analytics.reports.run",
            user_message="how's my website doing",
            task_state={},
            connected_integrations=["google_analytics"],
            plan=plan,
            step=step,
        )
    assert obs.connector_id == "google_analytics"
    assert obs.structured["connection_id"] == CONNECTION_ID

    obs.summary = "Analytics: 1,216 active users, 1,241 sessions (last week)"
    obs.structured.update({"active_users": 1216, "sessions": 1241})
    message = _compose_cross_source_message([obs])
    assert "1,216 active users" in message
    assert CONNECTION_ID not in message
    blocks = blocks_from_execution_observations([obs])
    assert blocks and blocks[0].title == "Google Analytics"


def test_prose_block_is_never_titled_with_an_id() -> None:
    blocks = blocks_from_execution_observations(
        [{"connector_id": CONNECTION_ID, "summary": "something", "success": True, "structured": {}}]
    )
    assert blocks[0].title == ""
