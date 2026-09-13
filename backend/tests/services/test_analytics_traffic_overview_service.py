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
        "app.connectors.google_analytics.run_ga4_report",
        side_effect=[fake_report, fake_report, source_report],
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
