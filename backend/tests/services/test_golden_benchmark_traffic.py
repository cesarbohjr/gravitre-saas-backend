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
from app.services.canonical_time_resolver import resolve_time_window, user_facing_time_label
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


D1_PROMPT = "Tell me about my GA4 website traffic."


def test_golden_d1_unique_ga4_property_auto_resolves_without_web_search() -> None:
    """R3 Test D-1 — exact confirmed incident: unique GA4 property, no Gravite web detour."""
    from app.services.adaptive_research_cascade import should_run_internet_research
    from app.services.analytics_traffic_overview_service import (
        is_analytics_traffic_overview_intent,
        should_suppress_knowledge_base_for_turn,
    )
    from app.services.clarification_policy import decide_from_resource_resolution
    from app.services.connector_resource_resolver import resolve_ga4_property

    assert is_analytics_traffic_overview_intent(D1_PROMPT) is True
    assert should_suppress_knowledge_base_for_turn(
        D1_PROMPT, connected_integrations=["google_analytics"]
    ) is True
    settings = SimpleNamespace(
        internet_research_enabled=True,
        tavily_api_key="tvly-test",
        serper_api_key="serper-test",
    )
    assert should_run_internet_research(
        "internet_research",
        settings=settings,
        internal_thin=True,
        query=D1_PROMPT,
    ) is False

    unique = ResourceResolution(
        status="resolved",
        connector_id="google_analytics",
        connection_id="conn-ga4",
        resource_type="property",
        resource_id="properties/123456789",
        display_name="Gravitre Isolated Test Site",
        candidate_count=1,
        resolution_reason="single_discovered_property",
    )
    decision = decide_from_resource_resolution(unique, resource_label="Google Analytics property")
    assert decision.should_ask is False
    assert "Gravitre Isolated Test Site" not in (decision.message or "")

    with patch(
        "app.services.connector_resource_resolver._connector_row",
        return_value={"id": "conn-ga4", "config": {}, "environment": "production"},
    ), patch(
        "app.connectors.google_analytics_oauth.ensure_google_analytics_session",
        return_value=("token", None),
    ), patch(
        "app.connectors.google_analytics.list_ga4_properties",
        return_value=[
            {
                "property_id": "properties/123456789",
                "display_name": "Gravitre Isolated Test Site",
                "default_uri": "https://alpha.test.gravitre.app",
            }
        ],
    ):
        resolution = resolve_ga4_property(
            client=MagicMock(),
            org_id="org-1",
            settings=SimpleNamespace(),
            environment_name="production",
        )
    assert resolution.status == "resolved"
    assert resolution.resource_id == "properties/123456789"
    assert resolution.resolution_reason == "single_discovered_property"
    assert resolution.candidate_count == 1


@pytest.mark.asyncio
async def test_golden_d1_overview_turn_does_not_ask_property_or_cite_gravite() -> None:
    unique = ResourceResolution(
        status="resolved",
        connector_id="google_analytics",
        connection_id="conn-ga4",
        resource_type="property",
        resource_id="properties/123456789",
        display_name="Gravitre Isolated Test Site",
        candidate_count=1,
        resolution_reason="single_discovered_property",
    )
    proof = SimpleNamespace(
        ok=True,
        error_class=None,
        user_message=lambda: "",
        compiled_parameters={
            "property_id": "properties/123456789",
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
        },
        resource={"name": "Gravitre Isolated Test Site"},
        time_window=None,
        status="ok",
    )
    invoked = SimpleNamespace(
        success=True,
        data={"metricHeaders": [], "rows": [], "totals": []},
        error_message=None,
    )
    with patch(
        "app.services.analytics_traffic_overview_service.resolve_resource",
        return_value=unique,
    ), patch(
        "app.services.analytics_traffic_overview_service.invoke_sealed_f1_read",
        return_value=(invoked, proof, None),
    ):
        turn = await try_analytics_traffic_overview_turn(
            message=D1_PROMPT,
            org_id="org-1",
            client=object(),
            settings=SimpleNamespace(),
            connected_integrations=["google_analytics"],
            task_state={},
        )
    assert turn is not None
    assert turn.get("stop_pipeline") is True
    assert turn.get("dialogue_mode") != "clarifying"
    msg = str(turn.get("message") or "")
    lowered = msg.lower()
    assert "which property" not in lowered
    assert "gravite" not in lowered
    assert "search the web" not in lowered
    assert "tavily" not in lowered
    assert "serper" not in lowered


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


def test_golden_i_last_month_label_is_not_last_30_days() -> None:
    from app.services.analytics_traffic_overview_service import _compose_overview_message

    window = resolve_time_window(ANCHOR, timezone_name="America/Los_Angeles", now=FROZEN)
    label = user_facing_time_label(window)
    empty = {"metricHeaders": [], "rows": [], "totals": []}
    message = _compose_overview_message(
        property_name="Acme site",
        current=empty,
        previous=empty,
        timeframe_label=label,
    )
    assert "last 30 days" not in message.lower()
    assert "august 2026" in message.lower()


@pytest.mark.parametrize(
    "query",
    [
        "How did the website do last month?",
        "Compare website traffic with August.",
        "What drove traffic last month?",
        "Show me traffic sources.",
        "Which pages performed best?",
        "How is organic search doing?",
        "How is our site doing?",
    ],
)
def test_golden_traffic_variants_share_canonical_time_when_last_month(query: str) -> None:
    window = resolve_time_window(query, timezone_name="America/Los_Angeles", now=FROZEN)
    if "last month" in query.lower() or "august" in query.lower():
        assert window is not None
        assert window.start.month == 8
        assert window.end.month == 8
        assert "30 days" not in user_facing_time_label(window).lower()
    label = user_facing_time_label(window) if window else ""
    assert "property_id" not in label


def test_react_compile_matches_sc_last_month_window() -> None:
    """General/ReAct path uses the same compiled calendar window as FAST_PATH."""
    window = resolve_time_window(ANCHOR, timezone_name="America/Los_Angeles", now=FROZEN)
    assert window is not None
    with patch("app.services.read_preflight.resolve_resource", return_value=_resolved()):
        result = preflight_read_action(context=_ctx())
    assert result.ok
    assert result.compiled_parameters["start_date"] == window.start_iso
    assert result.compiled_parameters["end_date"] == window.end_iso
