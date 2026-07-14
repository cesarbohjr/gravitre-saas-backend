"""Unit tests: Apollo discovery BYO-tier labeling (no executor changes)."""
from __future__ import annotations

from app.connectors.apollo_discovery_capability import (
    APOLLO_DISCOVERY_USER_MESSAGE,
    is_apollo_discovery_plan_limit_text,
)
from app.services.connector_capability_analysis import analyze_capability_gaps, capability_check_lines
from app.services.tool_error_messages import format_tool_error_for_user


def test_is_apollo_discovery_plan_limit_text_matches_sales_phase4_body():
    msg = (
        "Apollo API 403: /mixed_people/api_search — api/v1/mixed_people/api_search "
        "is not accessible with this access token on a free plan. "
        "Please upgrade your plan from https://app.apollo.io/."
    )
    assert is_apollo_discovery_plan_limit_text(msg)


def test_format_tool_error_maps_apollo_plan_limit_to_upgrade_copy():
    msg = format_tool_error_for_user(
        "permission_denied",
        "api/v1/mixed_people/api_search is not accessible with this access token on a free plan",
        integration="apollo",
        action="apollo.people.search",
        reason="apollo_plan_limit",
    )
    assert msg == APOLLO_DISCOVERY_USER_MESSAGE
    assert "app.apollo.io" in msg
    assert "permission" not in msg.lower() or "plan" in msg.lower()


def test_format_tool_error_generic_permission_denied_unchanged():
    msg = format_tool_error_for_user(
        "permission_denied",
        None,
        action="hubspot.deals.update",
        integration="hubspot",
    )
    assert "permission" in msg.lower()
    assert "app.apollo.io" not in msg


def test_capability_check_lines_apollo_search_requires_plan():
    gaps = analyze_capability_gaps("apollo")
    lines = capability_check_lines(
        gaps,
        vendor="apollo",
        capabilities=("search_people", "search_companies", "create_list"),
        plan_limited_discovery=True,
    )
    joined = "\n".join(lines)
    assert "Can search people?" in joined
    assert "requires: paid Apollo plan with search API access" in joined
