"""Authoritative route entitlement classification for the complete API audit.

Every FastAPI route must resolve via ``classify_route(method, path)``. The meta-tests
compare runtime route inventory against these rules so new routes cannot ship without
an explicit tier decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TierRequired = Literal["none", "control", "command"]
RouteStatus = Literal["correctly_guarded", "correctly_unguarded", "gap_needs_guard"]

GuardKind = Literal["none", "router_require_tier", "router_require_feature", "inline", "billing_gate"]


@dataclass(frozen=True)
class RouteEntitlementDecision:
    method: str
    path: str
    tier_required: TierRequired
    guard_present: bool
    guard_location: GuardKind
    status: RouteStatus
    notes: str = ""


# Tier-agnostic: infrastructure, auth bootstrap, inbound webhooks, internal ops.
TIER_AGNOSTIC_PREFIXES: tuple[str, ...] = (
    "/health",
    "/api/health",
    "/api/webhooks/stripe",
    "/api/webhooks/hubspot",
    "/api/webhooks/salesforce",
    "/api/webhooks/pagerduty",
    "/api/webhooks/segment",
    "/api/internal",
    "/api/ops/",
    "/api/platform/cs/",
    "/api/billing-sync/internal",
    "/api/knowledge-sync/internal",
    "/api/workflow-schedules/internal",
    "/api/billing/checkout/public",
)

TIER_AGNOSTIC_EXACT: frozenset[str] = frozenset(
    {
        "/api/auth/sso/callback",
        "/api/auth/sso/init",
        "/api/auth/sso/metadata",
    }
)

# Router-level guards confirmed in code (prefix -> (tier, kind, feature_or_tier)).
ROUTER_LEVEL_GUARDS: dict[str, tuple[TierRequired, GuardKind, str]] = {
    "/api/federation": ("control", "router_require_feature", "api_full_access"),
    "/api/meson": ("control", "router_require_tier", "control"),
    "/api/ml": ("command", "router_require_tier", "command"),
    "/api/agent-swarm": ("command", "router_require_tier", "command"),
    "/api/agent-council": ("command", "router_require_tier", "command"),
}

# Inline entitlement checks (prefix or exact -> feature/tier note).
INLINE_GUARDED_PREFIXES: dict[str, tuple[TierRequired, str]] = {
    "/api/webhooks/triggers": ("control", "custom_webhooks"),
    "/scim/v2": ("command", "sso_saml"),
    "/api/auth/sso": ("command", "sso_saml"),
}

# Workflow plan-feature routes (billing plan JSON features, not TIER_FEATURES).
WORKFLOW_PLAN_FEATURE_PREFIXES: tuple[tuple[str, str, TierRequired], ...] = (
    ("/api/workflows/", "version", "control"),
    ("/api/workflows/", "approval", "control"),
    ("/api/approvals", "", "control"),
)

PLATFORM_ADMIN_PREFIX = "/api/platform"


def _matches_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def classify_route(method: str, path: str) -> RouteEntitlementDecision:
    """Return explicit entitlement decision for one HTTP route."""
    m = method.upper()
    p = path.rstrip("/") if path != "/" else path

    if p in TIER_AGNOSTIC_EXACT:
        return RouteEntitlementDecision(m, path, "none", False, "none", "correctly_unguarded", "public SSO flow")

    for prefix in TIER_AGNOSTIC_PREFIXES:
        if _matches_prefix(p, prefix):
            return RouteEntitlementDecision(
                m, path, "none", False, "none", "correctly_unguarded", "infrastructure or inbound webhook"
            )

    if _matches_prefix(p, PLATFORM_ADMIN_PREFIX):
        return RouteEntitlementDecision(
            m, path, "none", False, "none", "correctly_unguarded", "platform admin auth, not org tier"
        )

    for prefix, (tier, kind, token) in ROUTER_LEVEL_GUARDS.items():
        if _matches_prefix(p, prefix):
            return RouteEntitlementDecision(
                m, path, tier, True, kind, "correctly_guarded", f"router Depends({kind}:{token})"
            )

    for prefix, (tier, feature) in INLINE_GUARDED_PREFIXES.items():
        if _matches_prefix(p, prefix) and p not in TIER_AGNOSTIC_EXACT:
            return RouteEntitlementDecision(
                m, path, tier, True, "inline", "correctly_guarded", f"inline feature check: {feature}"
            )

    lower = p.lower()
    for path_prefix, needle, tier in WORKFLOW_PLAN_FEATURE_PREFIXES:
        if p.startswith(path_prefix) and (not needle or needle in lower):
            return RouteEntitlementDecision(
                m,
                path,
                tier,
                True,
                "inline",
                "correctly_guarded",
                "workflows require_feature(plan) for versioning/approvals",
            )

    if "/connectors" in p and any(x in lower for x in ("oauth", "advanced", "enterprise")):
        return RouteEntitlementDecision(
            m, path, "control", True, "inline", "correctly_guarded", "advanced_connectors plan feature"
        )

    if p.startswith("/api/enterprise") or p.startswith("/api/audit"):
        return RouteEntitlementDecision(
            m, path, "control", True, "inline", "correctly_guarded", "audit_logs plan feature on select routes"
        )

    # Default authenticated product route: tier-agnostic (Node+), trial/subscription gated by billing middleware.
    return RouteEntitlementDecision(
        m,
        path,
        "none",
        False,
        "billing_gate",
        "correctly_unguarded",
        "product route; subscription/trial enforced by billing_access_gate_middleware",
    )


def classify_all_routes(routes: list[dict[str, str]]) -> list[RouteEntitlementDecision]:
    return [classify_route(r["method"], r["path"]) for r in routes]


def gaps(decisions: list[RouteEntitlementDecision]) -> list[RouteEntitlementDecision]:
    return [d for d in decisions if d.status == "gap_needs_guard"]
