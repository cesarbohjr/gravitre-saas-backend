"""Audit §33 / §34 item 8 — golden traffic benchmark (structural).

Anchor: "Tell me what my website traffic was last month."
Scenarios A–G are the CI gate. Live smoke is a separate isolated-org script.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.capability_ontology.recipe_resolver import resolve_recipe
from app.services.analytics_traffic_overview_service import (
    _compose_cross_source_message,
    try_analytics_traffic_overview_turn,
)
from app.services.canonical_time_resolver import resolve_time_window
from app.services.clarification_policy import decide_from_resource_resolution
from app.services.cognitive_execution_replanner import build_cross_source_analytics_plan
from app.services.connector_resource_resolver import ResourceResolution
from app.services.domain_property_binding import match_resource_to_domain
from app.services.execution_plan_service import ExecutionObservation
from app.services.read_preflight import preflight_read_action

ANCHOR = "Tell me what my website traffic was last month."
FROZEN = datetime(2026, 9, 16, 18, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
LEAK = ("property_id", "filter_groups", "action_key", "spec_revision", "preflight")


def _ctx(**overrides):
    base = {
        "org_id": "org-1",
        "client": MagicMock(),
        "settings": SimpleNamespace(),
        "environment_name": "production",
        "connected_integrations": ["google_analytics", "google_search_console"],
        "timezone": "America/Los_Angeles",
        "now": FROZEN,
        "business_identity": {"website": "https://acme.example", "timezone": "America/Los_Angeles"},
        "user_message": ANCHOR,
        "action_key": "google_analytics.reports.run",
        "proposed_args": {},
    }
    base.update(overrides)
    return base


def _resolved(rid: str = "123456") -> ResourceResolution:
    return ResourceResolution(
        status="resolved",
        connector_id="google_analytics",
        connection_id="conn-1",
        resource_type="property",
        resource_id=rid,
        display_name="Acme site",
        candidate_count=1,
        resolution_reason="linked_config",
    )


def test_golden_a_ga4_and_gsc_compile_month_without_clarify() -> None:
    window = resolve_time_window(
        ANCHOR,
        timezone_name="America/Los_Angeles",
        now=FROZEN,
    )
    assert window is not None
    assert window.start.isoformat() == "2026-08-01"
    assert window.end.isoformat() == "2026-08-31"
    assert window.interpretation == "previous_calendar_month"

    recipe = resolve_recipe(
        "analytics.website-traffic-overview",
        connected_integrations=["google_analytics", "google_search_console"],
        query=ANCHOR,
    )
    assert recipe is not None
    assert recipe.status == "fully_resolved"
    by_id = {s.step_id: s for s in recipe.steps}
    assert by_id["read_ga4"].resolved_action == "google_analytics.reports.run"
    assert by_id["read_gsc"].resolved_action == "google_search_console.searchAnalytics.query"

    with patch("app.services.read_preflight.resolve_resource", return_value=_resolved()):
        result = preflight_read_action(context=_ctx())
    assert result.ok, result.as_dict()
    assert result.compiled_parameters["start_date"] == "2026-08-01"
    assert result.compiled_parameters["end_date"] == "2026-08-31"
    assert result.error_class is None


def test_golden_b_three_properties_domain_match_auto_selects() -> None:
    matched = match_resource_to_domain(
        (
            {"property_id": "111", "display_name": "Acme", "default_uri": "https://acme.example", "org_id": "org-1"},
            {"property_id": "222", "display_name": "Docs", "default_uri": "https://docs.example", "org_id": "org-1"},
            {"property_id": "333", "display_name": "App", "default_uri": "https://app.example", "org_id": "org-1"},
        ),
        host="acme.example",
        org_id="org-1",
    )
    assert matched is not None
    assert matched["property_id"] == "111"
    decision = decide_from_resource_resolution(
        ResourceResolution(
            status="resolved",
            connector_id="google_analytics",
            resource_id="111",
            display_name="Acme",
            candidate_count=1,
        )
    )
    assert decision.should_ask is False


def test_golden_c_three_sites_clarify_with_display_names() -> None:
    resolution = ResourceResolution(
        status="ambiguous",
        connector_id="google_analytics",
        resource_type="property",
        candidate_count=3,
        candidates=(
            {"property_id": "1", "display_name": "Marketing site"},
            {"property_id": "2", "display_name": "Docs"},
            {"property_id": "3", "display_name": "App"},
        ),
    )
    decision = decide_from_resource_resolution(resolution, resource_label="property")
    assert decision.should_ask is True
    text = decision.message or ""
    assert "Marketing site" in text
    assert "Docs" in text
    assert "App" in text
    assert "property_id" not in text


def test_golden_d_auth_expired_does_not_ask_for_property() -> None:
    with patch(
        "app.services.read_preflight.resolve_resource",
        return_value=ResourceResolution(
            status="not_authorized",
            connector_id="google_analytics",
            resolution_reason="invalid_grant",
        ),
    ):
        result = preflight_read_action(context=_ctx())
    assert result.error_class == "AUTH_EXPIRED"
    msg = result.user_message().lower()
    assert "expired" in msg or "refresh" in msg or "re-author" in msg
    assert "property" not in msg
    decision = decide_from_resource_resolution(
        ResourceResolution(status="not_authorized", connector_id="google_analytics")
    )
    assert decision.should_ask is False
    assert "property" not in (decision.message or "").lower()


@pytest.mark.asyncio
async def test_golden_e_no_analytics_connects_without_web_search() -> None:
    turn = await try_analytics_traffic_overview_turn(
        message=ANCHOR,
        org_id="org-1",
        client=object(),
        connected_integrations=[],
        task_state={},
    )
    assert turn is not None
    assert turn.get("stop_pipeline") is True
    msg = str(turn.get("message") or "").lower()
    assert "connect" in msg
    assert turn.get("workflow_status") == "connector_not_connected"
    assert "search the web" not in msg
    assert "tavily" not in msg
    assert "internet" not in msg


def test_golden_f_recoverable_param_error_compiles_over_model_guess() -> None:
    with patch("app.services.read_preflight.resolve_resource", return_value=_resolved("123456")):
        result = preflight_read_action(
            context=_ctx(proposed_args={"property_id": "wrong-model-id", "start_date": "30daysAgo"})
        )
    assert result.ok, result.as_dict()
    assert result.compiled_parameters["property_id"] == "123456"
    assert result.compiled_parameters["start_date"] == "2026-08-01"
    assert result.shadow_diff
    assert result.shadow_diff["property_id"]["proposed"] == "wrong-model-id"


def test_golden_g_multi_source_user_copy_omits_vendor_names() -> None:
    plan = build_cross_source_analytics_plan(
        ANCHOR,
        capability_id="analytics.traffic_overview",
        connected_integrations=["google_analytics", "google_search_console"],
    )
    assert plan is not None
    assert {s.connector_id for s in plan.steps if s.kind == "read"} == {
        "google_analytics",
        "google_search_console",
    }
    message = _compose_cross_source_message(
        [
            ExecutionObservation(
                step_id="read_ga4",
                connector_id="google_analytics",
                success=True,
                summary="GA4: 1,200 active users, 900 sessions (2026-08-01–2026-08-31)",
            ),
            ExecutionObservation(
                step_id="read_gsc",
                connector_id="google_search_console",
                success=True,
                summary="Search Console: top page **/** (40 clicks, 28d)",
            ),
        ]
    )
    lowered = message.lower()
    assert "analytics:" in lowered
    assert "search:" in lowered
    assert "google analytics" not in lowered
    assert "search console" not in lowered
    assert "ga4" not in lowered
    for token in LEAK:
        assert token not in lowered
