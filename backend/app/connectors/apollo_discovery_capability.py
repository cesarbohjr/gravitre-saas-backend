"""Apollo discovery capability labeling — plan-tier probe (not executor changes).

Company/contact search APIs require a paid Apollo plan with search access.
List create often works on free plans. Probe detects the known free-plan 403
signature so install/setup can warn before a workflow fails mid-run.
"""
from __future__ import annotations

from typing import Any

from app.connectors.apollo_api import (
    ApolloAPIError,
    is_apollo_plan_limit_error,
    resolve_apollo_connector,
    search_organizations,
    search_people,
)

APOLLO_DISCOVERY_REQUIRES = "paid Apollo plan with search API access"

APOLLO_DISCOVERY_USER_MESSAGE = (
    "Company/contact discovery requires an Apollo plan with search API access — "
    "see https://app.apollo.io/ to upgrade"
)

APOLLO_DISCOVERY_CAPABILITY_NOTE = (
    "Can search companies/people? requires: paid Apollo plan with search API access "
    "(list create works without it)"
)

# Static catalog/marketplace note (shown even before a live probe).
APOLLO_DISCOVERY_REQUIREMENT_NOTE = (
    "Company/contact discovery requires your own Apollo plan with search API access "
    "(same BYO-tier pattern as ZoomInfo / LinkedIn Sales Navigator). "
    "Build ICP and Create list work with any connected Apollo account."
)


def is_apollo_discovery_plan_limit_text(text: str | None) -> bool:
    """True when vendor/error text matches the known free-plan search 403."""
    lowered = str(text or "").lower()
    if not lowered:
        return False
    markers = (
        "free plan",
        "upgrade your plan",
        "not accessible with this access token",
        "not accessible with this api_key",
        "mixed_people/api_search",
        "mixed_companies/search",
        "apollo_plan_limit",
    )
    return any(m in lowered for m in markers)


def probe_apollo_discovery_capabilities(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Any,
    *,
    environment_name: str | None = None,
) -> dict[str, Any]:
    """Live probe: can this connected Apollo run people/company search?

    Does not modify executors — calls the same HTTP search routes used by tools.
    Returns a capability map suitable for install checklist / connector availability.
    """
    base: dict[str, Any] = {
        "vendor": "apollo",
        "discoveryRequires": APOLLO_DISCOVERY_REQUIRES,
        "requirementNote": APOLLO_DISCOVERY_REQUIREMENT_NOTE,
        "userMessage": APOLLO_DISCOVERY_USER_MESSAGE,
        "capabilityNote": APOLLO_DISCOVERY_CAPABILITY_NOTE,
        "searchPeople": None,
        "searchCompanies": None,
        "planLimited": False,
        "probed": False,
        "error": None,
    }
    try:
        _cid, headers = resolve_apollo_connector(
            client,
            org_id,
            connector_id,
            settings,
            environment_name=environment_name,
        )
    except ApolloAPIError as exc:
        base["error"] = str(exc)
        if is_apollo_plan_limit_error(exc) or is_apollo_discovery_plan_limit_text(str(exc)):
            base["planLimited"] = True
            base["searchPeople"] = False
            base["searchCompanies"] = False
            base["probed"] = True
        return base
    except Exception as exc:  # noqa: BLE001
        base["error"] = f"{exc.__class__.__name__}: {exc}"
        return base

    people_ok = False
    companies_ok = False
    plan_limited = False

    try:
        search_people(headers, params={"per_page": 1})
        people_ok = True
    except ApolloAPIError as exc:
        if is_apollo_plan_limit_error(exc) or is_apollo_discovery_plan_limit_text(str(exc)):
            plan_limited = True
            people_ok = False
        else:
            base["error"] = str(exc)

    try:
        search_organizations(headers, params={"per_page": 1})
        companies_ok = True
    except ApolloAPIError as exc:
        if is_apollo_plan_limit_error(exc) or is_apollo_discovery_plan_limit_text(str(exc)):
            plan_limited = True
            companies_ok = False
        elif not base.get("error"):
            base["error"] = str(exc)

    base.update(
        {
            "probed": True,
            "searchPeople": people_ok,
            "searchCompanies": companies_ok,
            "planLimited": plan_limited,
        }
    )
    if plan_limited:
        base["warning"] = APOLLO_DISCOVERY_USER_MESSAGE
    return base
