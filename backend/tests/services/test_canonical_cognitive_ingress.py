"""Canonical Phase A ingress wiring — resolution selectivity and dedupe."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.canonical_cognitive_resolution import (
    apply_canonical_cognitive_resolution,
    assess_cognitive_resolution_needs,
    resolution_already_applied,
    try_analytics_short_circuit_turn,
)
from app.services.resolution_trace_service import ResolutionTraceBuilder


def test_chitchat_skips_resource_resolution() -> None:
    needs = assess_cognitive_resolution_needs("hello", {})
    assert needs.run_semantic is True
    assert needs.run_resource is False
    assert needs.reason == "chitchat"


def test_ga4_traffic_requests_resource_and_analytics_short_circuit() -> None:
    needs = assess_cognitive_resolution_needs(
        "Tell me about my GA4 website traffic",
        {},
        connected_integrations=["google_analytics"],
    )
    assert needs.run_resource is True
    assert needs.analytics_short_circuit is True


def test_yes_reference_skips_resource() -> None:
    state = {
        "offered_action": {
            "status": "awaiting_user_confirmation",
            "id": "offer-1",
        }
    }
    needs = assess_cognitive_resolution_needs("yes", state)
    assert needs.run_resource is False
    assert needs.reason == "reference_confirm"


def test_resolution_already_applied_matches_message() -> None:
    state = {
        "cognitive_resolution_message": "hello",
        "resolution_trace": {"stages": []},
    }
    assert resolution_already_applied(state, "hello") is True
    assert resolution_already_applied(state, "hi") is False


@pytest.mark.asyncio
async def test_apply_canonical_skips_resource_for_chitchat() -> None:
    with patch(
        "app.services.cognitive_resolution_pipeline.resolve_resource_request",
    ) as mock_resource:
        result, merged = await apply_canonical_cognitive_resolution(
            message="hello",
            task_state={},
            tenant_id="org-1",
            user_id="user-1",
            client=object(),
            connected_integrations=["google_analytics"],
        )
    assert result is not None
    assert merged.get("cognitive_resolution_message") == "hello"
    mock_resource.assert_not_called()


@pytest.mark.asyncio
async def test_analytics_short_circuit_respects_needs_flag() -> None:
    turn = await try_analytics_short_circuit_turn(
        message="Tell me about GA4 traffic",
        resolution=None,
        org_id="org-1",
        client=object(),
        settings=None,
        connected_integrations=["google_analytics"],
        task_state={"cognitive_resolution_needs": {"analytics_short_circuit": False}},
    )
    assert turn is None


@pytest.mark.asyncio
async def test_analytics_short_circuit_invokes_handler() -> None:
    expected = {"stop_pipeline": True, "message": "Traffic summary", "dialogue_mode": "answer"}
    with patch(
        "app.services.analytics_traffic_overview_service.try_analytics_traffic_overview_turn",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_turn:
        turn = await try_analytics_short_circuit_turn(
            message="Tell me about GA4 traffic",
            resolution=None,
            org_id="org-1",
            client=object(),
            settings=None,
            connected_integrations=["google_analytics"],
            task_state={
                "cognitive_resolution_needs": {"analytics_short_circuit": True},
            },
        )
    assert turn == expected
    mock_turn.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_turn_dedupes_cognitive_resolution() -> None:
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    trace = ResolutionTraceBuilder(conversation_id="conv-1", tenant_id="org-1").finish().as_dict()
    service = ChatConnectorExecutionService(settings=object())
    service._state = AsyncMock()
    service._state.update_task_state = AsyncMock()

    with patch(
        "app.services.cognitive_resolution_pipeline.run_cognitive_resolution",
        new_callable=AsyncMock,
    ) as mock_run:
        await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="hello",
            classification={},
            task_state={
                "cognitive_resolution_message": "hello",
                "resolution_trace": trace,
            },
            connected_integrations=[],
            client=object(),
        )
    mock_run.assert_not_awaited()
