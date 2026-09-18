"""PART 16–20 — analytics traffic business intent."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.analytics_traffic_overview_service import (
    detect_analytics_traffic_intent,
    is_analytics_traffic_overview_intent,
    should_suppress_knowledge_base_for_turn,
    try_analytics_traffic_overview_turn,
)
from app.services.chat_connector_execution_service import ChatConnectorExecutionService
from app.services.clarification_policy import decide_resource_clarification
from app.services.execution_plan_service import ExecutionObservation
from app.services.tool_types import NormalizedResult


def _sealed_reports(current: dict, source: dict):
    def _call(*, step, **_kwargs):
        proof = SimpleNamespace(
            ok=True,
            status="ready",
            compiled_parameters={"property_id": "123", "start_date": "30daysAgo", "end_date": "today"},
            resource={"name": "Gravitre Website", "id": "123", "reason": "linked_config"},
            time_window={"interpretation": "action_spec_default"},
            user_message=lambda: "",
            error_class=None,
            as_dict=lambda: {},
            connector_id="google_analytics",
            capability_id="analytics.traffic_overview",
        )
        data = source if "source" in str(step.step_id) else current
        invoked = NormalizedResult(success=True, action="analytics.reports.run", data=data)
        obs = ExecutionObservation(
            step_id=step.step_id,
            connector_id="google_analytics",
            success=True,
            summary="ok",
            plan_id="plan-1",
        )
        return invoked, proof, obs

    return _call


def test_is_analytics_traffic_overview_intent_matches_screenshot_prompt() -> None:
    assert is_analytics_traffic_overview_intent("Tell me about my GA4 website traffic.")


def test_detect_intent_when_ga_connected() -> None:
    intent = detect_analytics_traffic_intent(
        "Tell me about my GA4 website traffic.",
        connected_integrations=["google_analytics", "hubspot"],
    )
    assert intent is not None
    assert intent.connector_id == "google_analytics"


def test_is_connector_intent_accepts_tell_me_about() -> None:
    assert ChatConnectorExecutionService.is_connector_intent(
        "Tell me about my GA4 website traffic.",
        {},
    )


def test_kb_suppressed_for_resolvable_analytics_turn() -> None:
    assert should_suppress_knowledge_base_for_turn(
        "Tell me about my GA4 website traffic.",
        connected_integrations=["google_analytics"],
    )


@pytest.mark.asyncio
async def test_not_connected_message() -> None:
    turn = await try_analytics_traffic_overview_turn(
        message="Tell me about my GA4 website traffic.",
        org_id="org-1",
        client=object(),
        settings=SimpleNamespace(),
        connected_integrations=["hubspot"],
        task_state={},
    )
    assert turn is not None
    assert turn.get("stop_pipeline") is True
    assert "isn't connected" in str(turn.get("message") or "").lower()


@pytest.mark.asyncio
async def test_single_property_auto_executes_without_clarification() -> None:
    fake_report = {
        "metricHeaders": [
            {"name": "activeUsers"},
            {"name": "sessions"},
            {"name": "screenPageViews"},
        ],
        "totals": [{"metricValues": [{"value": "100"}, {"value": "120"}, {"value": "300"}]}],
        "rows": [],
    }
    source_report = {
        "rows": [{"dimensionValues": [{"value": "Organic Search"}], "metricValues": [{"value": "50"}]}],
        "metricHeaders": [{"name": "sessions"}],
    }
    with patch(
        "app.services.analytics_traffic_overview_service.resolve_resource",
        return_value=SimpleNamespace(
            status="resolved",
            resource_id="123",
            display_name="Gravitre Website",
            connection_id="conn-1",
            resolution_reason="linked_config",
            candidate_count=1,
            connector_id="google_analytics",
            resource_type="property",
        ),
    ), patch(
        "app.connectors.google_analytics_oauth.ensure_google_analytics_session",
        return_value=("token", None),
    ), patch(
        "app.services.analytics_traffic_overview_service.invoke_sealed_f1_read",
        side_effect=_sealed_reports(fake_report, source_report),
    ):
        turn = await try_analytics_traffic_overview_turn(
            message="Tell me about my GA4 website traffic.",
            org_id="org-1",
            client=object(),
            settings=SimpleNamespace(),
            connected_integrations=["google_analytics"],
            task_state={},
        )
    assert turn is not None
    assert turn.get("stop_pipeline") is True
    message = str(turn.get("message") or "")
    assert "last 30 days" in message.lower()
    assert "Active users" in message
    assert "property" not in message.lower() or "gravitre website" in message.lower()
    assert "which one should i use" not in message.lower()
    assert "need the exact property" not in message.lower()


def test_multi_property_clarification_is_legitimate() -> None:
    decision = decide_resource_clarification(
        candidate_count=3,
        candidate_labels=["Gravitre", "Customer Portal", "Documentation"],
        resource_label="Google Analytics property",
    )
    assert decision.should_ask is True
    assert "Gravitre" in (decision.message or "")
    assert "Documentation" in (decision.message or "")


@pytest.mark.asyncio
async def test_ambiguous_property_returns_named_clarification() -> None:
    with patch(
        "app.services.analytics_traffic_overview_service.resolve_resource",
        return_value=SimpleNamespace(
            status="ambiguous",
            candidate_count=3,
            candidates=(
                {"display_name": "Gravitre"},
                {"display_name": "Customer Portal"},
                {"display_name": "Documentation"},
            ),
            connection_id="conn-1",
            connector_id="google_analytics",
            resource_type="property",
        ),
    ):
        turn = await try_analytics_traffic_overview_turn(
            message="Tell me about my GA4 website traffic.",
            org_id="org-1",
            client=object(),
            settings=SimpleNamespace(),
            connected_integrations=["google_analytics"],
            task_state={},
        )
    assert turn is not None
    assert turn.get("dialogue_mode") == "clarifying"
    assert "three" in str(turn.get("message") or "").lower() or "3" in str(turn.get("message") or "")


@pytest.mark.asyncio
async def test_e1_resolved_resource_skips_second_discovery() -> None:
    fake_report = {
        "metricHeaders": [{"name": "activeUsers"}, {"name": "sessions"}, {"name": "screenPageViews"}],
        "totals": [{"metricValues": [{"value": "100"}, {"value": "120"}, {"value": "300"}]}],
        "rows": [],
    }
    with patch(
        "app.services.analytics_traffic_overview_service.resolve_resource",
        side_effect=AssertionError("duplicate resource discovery"),
    ), patch(
        "app.services.analytics_traffic_overview_service.invoke_sealed_f1_read",
        side_effect=_sealed_reports(fake_report, {"rows": []}),
    ):
        turn = await try_analytics_traffic_overview_turn(
            message="Tell me what my website traffic was last month.",
            org_id="org-1",
            client=object(),
            settings=SimpleNamespace(),
            connected_integrations=["google_analytics"],
            task_state={
                "cognitive_resolution_needs": {"analytics_short_circuit": True},
                "e1_resource": {
                    "status": "resolved",
                    "connector_id": "google_analytics",
                    "resource_id": "123",
                    "display_name": "Gravitre Website",
                    "resolution_reason": "e1",
                    "candidate_count": 1,
                    "connection_id": "conn-1",
                    "resource_type": "property",
                },
            },
        )
    assert turn is not None
    assert turn.get("execution_strategy") == "FAST_PATH"
    assert turn.get("plan_terminal_status") == "completed"
