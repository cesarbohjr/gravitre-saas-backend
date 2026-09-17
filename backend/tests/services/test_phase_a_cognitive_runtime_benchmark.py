"""Phase A mandatory regression scenarios (A–J)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.analytics_traffic_overview_service import (
    detect_analytics_traffic_intent,
    try_analytics_traffic_overview_turn,
)
from app.services.clarification_policy import decide_from_resource_resolution
from app.services.connector_resource_resolver import ResourceResolution
from app.services.connector_semantic_registry import (
    resolve_analytics_capabilities_for_message,
    resolve_connector_from_text,
)
from app.services.reference_resolver import resolve_reference, store_option_set
from app.services.resolution_trace_service import ResolutionTraceBuilder


@pytest.mark.asyncio
async def test_scenario_a_ga4_traffic_single_property_auto_select() -> None:
    """SCENARIO A — GA4 traffic, one property, no clarification."""
    resolution = ResourceResolution(
        status="resolved",
        connector_id="google_analytics",
        connection_id="conn-1",
        resource_type="property",
        resource_id="123",
        display_name="Main Site",
        candidate_count=1,
        resolution_reason="linked_config",
    )
    with patch(
        "app.services.analytics_traffic_overview_service.resolve_resource",
        return_value=resolution,
    ), patch(
        "app.services.read_preflight.resolve_resource",
        return_value=resolution,
    ), patch(
        "app.connectors.google_analytics_oauth.ensure_google_analytics_session",
        return_value=("token", None),
    ), patch(
        "app.connectors.google_analytics.run_ga4_report",
        return_value={"metricHeaders": [], "rows": [], "totals": []},
    ):
        turn = await try_analytics_traffic_overview_turn(
            message="Tell me about my GA4 website traffic.",
            org_id="org-1",
            client=object(),
            connected_integrations=["google_analytics"],
            task_state={},
        )
    assert turn is not None
    assert turn.get("stop_pipeline") is True
    assert "Which" not in str(turn.get("message") or "")
    assert "google_analytics" not in str(turn.get("message") or "").lower()


def test_scenario_b_website_doing_identifies_analytics_capabilities() -> None:
    """SCENARIO B — website performance with GA4 + GSC connected."""
    caps = resolve_analytics_capabilities_for_message(
        "How is my website doing?",
        connected_integrations=["google_analytics", "google_search_console"],
    )
    assert "google_analytics" in caps
    assert "google_search_console" in caps
    intent = detect_analytics_traffic_intent(
        "How is my website doing?",
        connected_integrations=["google_analytics", "google_search_console"],
    )
    assert intent is not None
    assert intent.connector_id == "google_analytics"


def test_scenario_c_yes_confirms_pending_offered_action() -> None:
    """SCENARIO C — yes resolves to pending offered action."""
    state = {
        "offered_action": {
            "id": "offer-1",
            "status": "awaiting_user_confirmation",
            "tools": ["connector_status"],
            "scope": ["connectors"],
        }
    }
    ref = resolve_reference("yes", state)
    assert ref.matched is True
    assert ref.kind == "confirm"
    assert ref.pending_target == "offered_action"


def test_scenario_d_all_three_selects_all_options() -> None:
    """SCENARIO D — all 3 selects every presented option."""
    options = [
        {"id": "realtime", "label": "Realtime"},
        {"id": "date_range", "label": "Date range"},
        {"id": "source_medium", "label": "Source/medium"},
    ]
    state = store_option_set({}, options)
    ref = resolve_reference("all 3", state)
    assert ref.matched is True
    assert ref.kind == "select_all_options"
    assert len(ref.selected_indices) == 3


def test_scenario_e_that_resolves_prior_analysis() -> None:
    """SCENARIO E — that resolves to prior analysis."""
    state = {
        "active_analysis": {
            "kind": "analytics.traffic_overview",
            "connector_id": "google_analytics",
            "property_id": "123",
        }
    }
    ref = resolve_reference("compare that to last month", state)
    assert ref.matched is True
    assert ref.kind == "referent"
    assert ref.referent.get("property_id") == "123"


def test_scenario_f_multiple_ga_properties_clarify_only_when_ambiguous() -> None:
    """SCENARIO F — multiple properties → clarification when ambiguous."""
    resolution = ResourceResolution(
        status="ambiguous",
        connector_id="google_analytics",
        resource_type="property",
        candidate_count=3,
        candidates=(
            {"property_id": "1", "display_name": "A"},
            {"property_id": "2", "display_name": "B"},
            {"property_id": "3", "display_name": "C"},
        ),
    )
    decision = decide_from_resource_resolution(resolution, resource_label="property")
    assert decision.should_ask is True

    single = ResourceResolution(
        status="resolved",
        connector_id="google_analytics",
        resource_type="property",
        resource_id="1",
        candidate_count=1,
    )
    assert decide_from_resource_resolution(single).should_ask is False


@pytest.mark.asyncio
async def test_scenario_g_no_ga_connection_clear_message() -> None:
    """SCENARIO G — no GA connection."""
    turn = await try_analytics_traffic_overview_turn(
        message="show my GA4 traffic",
        org_id="org-1",
        client=object(),
        connected_integrations=[],
        task_state={},
    )
    assert turn is not None
    msg = str(turn.get("message") or "").lower()
    assert "connect" in msg
    assert turn.get("workflow_status") == "connector_not_connected"


@pytest.mark.parametrize(
    "message,expected",
    [
        ("GA", "google_analytics"),
        ("QBO", "quickbooks"),
        ("SFDC", "salesforce"),
    ],
)
def test_scenario_h_i_j_alias_resolution(message: str, expected: str) -> None:
    assert resolve_connector_from_text(message) == expected


def test_resolution_trace_stages_present() -> None:
    builder = ResolutionTraceBuilder(conversation_id="c1", tenant_id="t1")
    builder.mark("turn_received")
    builder.mark("semantic_resolution_start")
    builder.set_connector("google_analytics")
    builder.mark("resource_resolution_start")
    builder.set_resource(resource_id="123", candidate_count=1, reason="linked_config")
    builder.set_clarification(False, "auto_selected_single")
    trace = builder.finish()
    stage_names = [record.stage for record in trace.stages]
    assert "semantic_resolution_complete" in stage_names or "connector_resolved" in stage_names
    assert "resolution_terminal" in stage_names


@pytest.mark.asyncio
async def test_cognitive_resolution_pipeline_wires_trace() -> None:
    from app.services.cognitive_resolution_pipeline import run_cognitive_resolution

    with patch(
        "app.services.cognitive_resolution_pipeline.resolve_resource_request",
        return_value=ResourceResolution(
            status="resolved",
            connector_id="google_analytics",
            resource_id="99",
            candidate_count=1,
            resolution_reason="linked_config",
        ),
    ):
        result = await run_cognitive_resolution(
            message="show GA4 traffic",
            task_state={},
            tenant_id="org-1",
            user_id="user-1",
            client=object(),
            conversation_id="conv-1",
            connected_integrations=["google_analytics"],
        )
    assert result.connector_id == "google_analytics"
    assert result.trace.resolved_connector_id == "google_analytics"
    assert result.clarification is not None
    assert result.clarification.should_ask is False
