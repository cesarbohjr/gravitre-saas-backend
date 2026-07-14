"""Apollo discovery capability labeling — plan-tier messaging (not executor changes).

Company/contact search APIs require a paid Apollo plan with search access.
List create often works on free plans. Live probing lives in apollo_tools
(governed execution layer); this module owns the shared BYO copy/constants.
"""
from __future__ import annotations

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
    client: object,
    org_id: str,
    connector_id: str,
    settings: object,
    *,
    environment_name: str | None = None,
) -> dict:
    """Delegate live probe to governed apollo_tools (no raw apollo_api import here)."""
    from app.services.apollo_tools import probe_apollo_discovery_capabilities as _probe

    return _probe(
        client,
        org_id,
        connector_id,
        settings,
        environment_name=environment_name,
    )
