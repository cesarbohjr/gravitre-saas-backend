"""F2 READ repair — sibling fallback and GA4→GSC auth fallback."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.f2_read_repair import repair_blocked_read
from app.services.read_preflight import PreflightResult
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        environment_name="production",
    )


def test_wrong_sibling_listing_falls_back_to_deals_list() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="hubspot.deals.search",
        error_class="WRONG_SIBLING_ACTION",
        org_id="org-1",
    )
    repaired = repair_blocked_read(
        blocked=blocked,
        ctx=_ctx(),
        invoke_action="hubspot.deals.search",
        args={},
        user_message="List my deals.",
        connected_integrations=["hubspot"],
    )
    assert repaired is not None
    assert repaired.action == "hubspot.deals.list"
    assert repaired.reason == "sibling_list_fallback"


def test_structured_search_does_not_convert_to_list() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="hubspot.deals.search",
        error_class="WRONG_SIBLING_ACTION",
        org_id="org-1",
    )
    repaired = repair_blocked_read(
        blocked=blocked,
        ctx=_ctx(),
        invoke_action="hubspot.deals.search",
        args={},
        user_message="Find high-value deals over ten thousand.",
        connected_integrations=["hubspot"],
    )
    assert repaired is None


def test_ga4_auth_expired_falls_back_to_gsc_when_preflight_ok() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="google_analytics.reports.run",
        error_class="AUTH_EXPIRED",
        org_id="org-1",
    )
    ok = PreflightResult(
        status="ready",
        action_key="google_search_console.searchAnalytics.query",
        compiled_parameters={"site_url": "https://acme.example/", "start_date": "2026-08-01", "end_date": "2026-08-31"},
        org_id="org-1",
        proof_digest="abc",
    )
    ok.status = "ready"
    with patch("app.services.f2_read_repair.preflight_read_action", return_value=ok):
        repaired = repair_blocked_read(
            blocked=blocked,
            ctx=_ctx(),
            invoke_action="analytics.reports.run",
            args={},
            user_message="Tell me what my website traffic was last month.",
            connected_integrations=["google_analytics", "google_search_console"],
        )
    assert repaired is not None
    assert repaired.reason == "ga4_auth_fallback_gsc"
    assert repaired.action == "searchconsole.searchAnalytics.query"
    assert repaired.preflight is ok


def test_ga4_auth_does_not_fallback_without_gsc() -> None:
    blocked = PreflightResult(
        status="blocked",
        action_key="google_analytics.reports.run",
        error_class="AUTH_EXPIRED",
        org_id="org-1",
    )
    repaired = repair_blocked_read(
        blocked=blocked,
        ctx=_ctx(),
        invoke_action="analytics.reports.run",
        args={},
        user_message="Tell me what my website traffic was last month.",
        connected_integrations=["google_analytics"],
    )
    assert repaired is None
