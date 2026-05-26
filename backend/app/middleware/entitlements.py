from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Callable

from fastapi import Depends, HTTPException, status
from supabase import create_client

from app.auth.dependencies import get_org_context
from app.config import Settings, get_settings
from app.core.errors import error_detail

TierName = str

TIER_ORDER: dict[TierName, int] = {
    "free": 0,
    "node": 1,
    "control": 2,
    "command": 3,
}

TIER_LIMITS: dict[TierName, dict[str, int | None]] = {
    "free": {
        "workflows": 3,
        "agents": 1,
        "connectors": 2,
        "runs_per_month": 200,
        "operator_sessions_concurrent": 1,
        "lite_seats_included": 0,
    },
    "node": {
        "workflows": 10,
        "agents": 2,
        "connectors": 5,
        "runs_per_month": 1000,
        "operator_sessions_concurrent": 1,
        "lite_seats_included": 0,
    },
    "control": {
        "workflows": 50,
        "agents": 10,
        "connectors": 20,
        "runs_per_month": 10000,
        "operator_sessions_concurrent": 5,
        "lite_seats_included": 5,
    },
    "command": {
        "workflows": None,
        "agents": None,
        "connectors": None,
        "runs_per_month": None,
        "operator_sessions_concurrent": None,
        "lite_seats_included": 25,
    },
}

TIER_FEATURES: dict[TierName, dict[str, bool]] = {
    "free": {
        "custom_webhooks": False,
        "sso_saml": False,
        "api_full_access": False,
        "priority_support_email": False,
        "priority_support_dedicated": False,
    },
    "node": {
        "custom_webhooks": False,
        "sso_saml": False,
        "api_full_access": False,
        "priority_support_email": False,
        "priority_support_dedicated": False,
    },
    "control": {
        "custom_webhooks": True,
        "sso_saml": False,
        "api_full_access": True,
        "priority_support_email": True,
        "priority_support_dedicated": False,
    },
    "command": {
        "custom_webhooks": True,
        "sso_saml": True,
        "api_full_access": True,
        "priority_support_email": True,
        "priority_support_dedicated": True,
    },
}


def _normalize_tier(raw_tier: str | None) -> TierName:
    value = (raw_tier or "free").strip().lower()
    if value in {"starter"}:
        return "node"
    if value in {"growth"}:
        return "control"
    if value in {"scale", "enterprise"}:
        return "command"
    if value not in TIER_ORDER:
        return "free"
    return value


def _select_latest_subscription(client, org_id: str) -> dict[str, Any] | None:
    response = (
        client.table("subscriptions")
        .select("*")
        .eq("org_id", org_id)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if response.data:
        return dict(response.data[0])
    return None


def _fallback_org_billing(client, org_id: str) -> dict[str, Any] | None:
    response = (
        client.table("org_billing")
        .select("plan_code, billing_status")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    row = response.data[0]
    return {
        "tier": _normalize_tier(row.get("plan_code")),
        "status": row.get("billing_status") or "trialing",
        "seat_count": 1,
        "lite_seats": 0,
        "meson_addons": [],
    }


def _month_start_iso() -> str:
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    return month_start.isoformat()


def _usage_totals(client, org_id: str) -> dict[str, int]:
    month_start = _month_start_iso()
    records = (
        client.table("usage_records")
        .select("metric_type, quantity")
        .eq("org_id", org_id)
        .gte("recorded_at", month_start)
        .execute()
        .data
        or []
    )
    totals: dict[str, int] = {}
    for row in records:
        metric = str(row.get("metric_type") or "").strip().lower()
        qty = int(row.get("quantity") or 0)
        totals[metric] = totals.get(metric, 0) + qty
    return totals


def resolve_entitlements(settings: Settings, org_id: str) -> dict[str, Any]:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    subscription = _select_latest_subscription(client, org_id)
    if subscription:
        tier = _normalize_tier(subscription.get("tier"))
        status = str(subscription.get("status") or "inactive")
        seat_count = int(subscription.get("seat_count") or 1)
        lite_seats = int(subscription.get("lite_seats") or 0)
        addons = subscription.get("meson_addons") or []
    else:
        fallback = _fallback_org_billing(client, org_id) or {
            "tier": "free",
            "status": "inactive",
            "seat_count": 1,
            "lite_seats": 0,
            "meson_addons": [],
        }
        tier = _normalize_tier(str(fallback["tier"]))
        status = str(fallback["status"])
        seat_count = int(fallback["seat_count"])
        lite_seats = int(fallback["lite_seats"])
        addons = fallback["meson_addons"]

    limits = dict(TIER_LIMITS.get(tier, TIER_LIMITS["free"]))
    limits["lite_seats_included"] = max(int(limits.get("lite_seats_included") or 0), lite_seats)
    features = dict(TIER_FEATURES.get(tier, TIER_FEATURES["free"]))
    usage = _usage_totals(client, org_id)
    return {
        "tier": tier,
        "status": status,
        "seat_count": seat_count,
        "lite_seats": lite_seats,
        "limits": limits,
        "features": features,
        "addons": addons if isinstance(addons, list) else [],
        "usage": usage,
    }


def _assert_tier(actual: str, minimum: str) -> None:
    if TIER_ORDER.get(actual, 0) < TIER_ORDER.get(minimum, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Upgrade required", "UNAUTHORIZED", {"required_tier": minimum}),
        )


def _assert_feature(entitlements: dict[str, Any], feature_name: str) -> None:
    features = entitlements.get("features") or {}
    if not bool(features.get(feature_name)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Feature unavailable", "UNAUTHORIZED", {"feature": feature_name}),
        )


def _assert_quota(entitlements: dict[str, Any], resource_name: str, current_value: int) -> None:
    limits = entitlements.get("limits") or {}
    limit = limits.get(resource_name)
    if limit is None:
        return
    if int(current_value) >= int(limit):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Quota exceeded", "VALIDATION_ERROR", {"resource": resource_name, "limit": limit}),
        )


async def get_entitlements_dependency(
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return resolve_entitlements(settings, org_id)


def require_tier(minimum_tier: str) -> Callable[..., Any]:
    async def dependency(
        entitlements: Annotated[dict[str, Any], Depends(get_entitlements_dependency)],
    ) -> dict[str, Any]:
        _assert_tier(str(entitlements.get("tier") or "free"), minimum_tier)
        return entitlements

    return dependency


def require_feature(feature_name: str) -> Callable[..., Any]:
    async def dependency(
        entitlements: Annotated[dict[str, Any], Depends(get_entitlements_dependency)],
    ) -> dict[str, Any]:
        _assert_feature(entitlements, feature_name)
        return entitlements

    return dependency


def check_quota(resource_name: str, current_value_fn: Callable[[dict[str, Any]], int]) -> Callable[..., Any]:
    async def dependency(
        entitlements: Annotated[dict[str, Any], Depends(get_entitlements_dependency)],
    ) -> dict[str, Any]:
        _assert_quota(entitlements, resource_name, current_value_fn(entitlements))
        return entitlements

    return dependency
