from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Callable

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user, get_org_context
from app.billing.seat_context import assert_full_seat, resolve_seat_context
from app.billing.service import get_org_billing, get_plan_for_org, get_supabase_client
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.core.safe_dict import safe_normalize_stored_dict

TierName = str

# Meson addon catalog codes → entitlement feature flags (decision C1).
MESON_ADDON_FEATURE_FLAGS: dict[str, str] = {
    "advanced_analytics": "meson_addon_advanced_analytics",
    "custom_model_training": "meson_addon_custom_model_training",
    "voice_interface": "meson_addon_voice_interface",
    "multi_language": "meson_addon_multi_language",
    "compliance_pack": "meson_addon_compliance_pack",
}

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
        "agents": 1,
        "connectors": 5,
        "runs_per_month": 500,
        "operator_sessions_concurrent": 1,
        "lite_seats_included": 2,
    },
    "control": {
        "workflows": 40,
        "agents": 3,
        "connectors": 20,
        "runs_per_month": 2500,
        "operator_sessions_concurrent": 5,
        "lite_seats_included": 5,
    },
    "command": {
        "workflows": 120,
        "agents": 8,
        "connectors": None,
        "runs_per_month": 10000,
        "operator_sessions_concurrent": None,
        "lite_seats_included": None,
    },
}

TIER_FEATURES: dict[TierName, dict[str, bool]] = {
    "free": {
        "custom_webhooks": False,
        "sso_saml": False,
        "api_full_access": False,
        "priority_support_email": False,
        "priority_support_dedicated": False,
        "cross_department_agents": False,
    },
    "node": {
        "custom_webhooks": False,
        "sso_saml": False,
        "api_full_access": False,
        "priority_support_email": False,
        "priority_support_dedicated": False,
        "cross_department_agents": False,
    },
    "control": {
        "custom_webhooks": True,
        "sso_saml": False,
        "api_full_access": True,
        "priority_support_email": True,
        "priority_support_dedicated": False,
        "cross_department_agents": False,
    },
    "command": {
        "custom_webhooks": True,
        "sso_saml": True,
        "api_full_access": True,
        "priority_support_email": True,
        "priority_support_dedicated": True,
        "cross_department_agents": True,
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


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "false", "none", "off", "0"}
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def resolve_entitlements(settings: Settings, org_id: str) -> dict[str, Any]:
    """Resolve tier/limits from org_billing + billing_plans (same SoT as Billing UI)."""
    client = get_supabase_client(settings)
    plan = get_plan_for_org(client, org_id)
    org_billing = get_org_billing(client, org_id) or {}
    subscription = _select_latest_subscription(client, org_id)

    tier = _normalize_tier(str(plan.get("code") or org_billing.get("plan_code") or "free"))
    status = str(
        org_billing.get("billing_status")
        or (subscription or {}).get("status")
        or "inactive"
    )
    seat_count = int((subscription or {}).get("seat_count") or 1)
    lite_seats_purchased = int((subscription or {}).get("lite_seats") or 0)
    addons_raw = (subscription or {}).get("meson_addons") or []
    addons = [str(a) for a in addons_raw] if isinstance(addons_raw, list) else []

    tier_defaults = safe_normalize_stored_dict(TIER_LIMITS.get(tier, TIER_LIMITS["free"]))
    plan_features = safe_normalize_stored_dict(plan.get("features"))
    # E1: plan features.lite_users is SoT for included Lite seats (−1 / None = unlimited).
    plan_lite = plan_features.get("lite_users", tier_defaults.get("lite_seats_included"))
    if plan_lite is None or plan_lite is False:
        lite_seats_included: int | None = int(tier_defaults.get("lite_seats_included") or 0)
    elif isinstance(plan_lite, (int, float)) and int(plan_lite) < 0:
        lite_seats_included = None
    else:
        lite_seats_included = int(plan_lite)
    limits = {
        "workflows": plan.get("workflows_limit", tier_defaults.get("workflows")),
        "agents": plan.get("agents_limit", tier_defaults.get("agents")),
        "connectors": tier_defaults.get("connectors"),
        "runs_per_month": plan.get("workflow_runs_included", tier_defaults.get("runs_per_month")),
        "operator_sessions_concurrent": tier_defaults.get("operator_sessions_concurrent"),
        "lite_seats_included": lite_seats_included,
        "environments": plan.get("environments_limit"),
        "ai_credits_included": plan.get("ai_credits_included"),
        "workflow_runs_included": plan.get("workflow_runs_included"),
    }
    features_source = TIER_FEATURES[tier] if tier in TIER_FEATURES else TIER_FEATURES["free"]
    features = {
        **dict(features_source),
        "approvals": _as_bool(plan_features.get("approvals", features_source.get("approvals"))),
        "audit_logs": _as_bool(plan_features.get("audit_logs", features_source.get("audit_logs"))),
        "versioning": _as_bool(plan_features.get("versioning", features_source.get("versioning"))),
        "advanced_connectors": _as_bool(
            plan_features.get("advanced_connectors", features_source.get("advanced_connectors"))
        ),
        "rbac": _as_bool(plan_features.get("rbac", features_source.get("rbac"))),
        "custom_webhooks": _as_bool(
            plan_features.get("advanced_connectors", features_source.get("custom_webhooks"))
        ),
        # Builder Meson requires Control+ plan allotment (not seat type).
        "meson_builder": bool(plan_features.get("meson"))
        or TIER_ORDER.get(tier, 0) >= TIER_ORDER["control"],
    }
    # C1: enabled Meson addon codes become real feature flags.
    for code in addons:
        flag = MESON_ADDON_FEATURE_FLAGS.get(code) or f"meson_addon_{code}"
        features[flag] = True
    usage = _usage_totals(client, org_id)
    return {
        "tier": tier,
        "status": status,
        "seat_count": seat_count,
        "lite_seats": lite_seats_purchased,
        "limits": limits,
        "features": features,
        "addons": addons,
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


def require_addon(addon_code: str) -> Callable[..., Any]:
    """C1: Meson addon catalog codes are real authorization gates."""

    async def dependency(
        entitlements: Annotated[dict[str, Any], Depends(get_entitlements_dependency)],
    ) -> dict[str, Any]:
        addons = {str(a) for a in (entitlements.get("addons") or [])}
        if addon_code not in addons:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_detail(
                    "Meson addon required",
                    "UNAUTHORIZED",
                    {"addon": addon_code},
                ),
            )
        return entitlements

    return dependency


def require_full_seat(*, action: str = "build") -> Callable[..., Any]:
    """A1: Lite seats cannot call BUILD / Meson-build surfaces."""

    async def dependency(
        current_user: Annotated[dict, Depends(get_current_user)],
        org_id: Annotated[str | None, Depends(get_org_context)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, Any]:
        if not org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
        client = get_supabase_client(settings)
        seat = resolve_seat_context(
            client, org_id=org_id, user_id=str(current_user.get("user_id") or "")
        )
        assert_full_seat(seat, action=action)
        return seat

    return dependency


def require_voice_configure() -> Callable[..., Any]:
    """B1 voice: CONFIGURE (assign voice / design / turn-taking) — full or manager seat."""

    async def dependency(
        current_user: Annotated[dict, Depends(get_current_user)],
        org_id: Annotated[str | None, Depends(get_org_context)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, Any]:
        from app.billing.seat_context import assert_voice_configure

        if not org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
        client = get_supabase_client(settings)
        seat = resolve_seat_context(
            client, org_id=org_id, user_id=str(current_user.get("user_id") or "")
        )
        assert_voice_configure(seat)
        return seat

    return dependency


def require_seat_context() -> Callable[..., Any]:
    """Resolve seat without asserting — for USE paths that branch on is_lite."""

    async def dependency(
        current_user: Annotated[dict, Depends(get_current_user)],
        org_id: Annotated[str | None, Depends(get_org_context)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, Any]:
        if not org_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
        client = get_supabase_client(settings)
        return resolve_seat_context(
            client, org_id=org_id, user_id=str(current_user.get("user_id") or "")
        )

    return dependency


def check_quota(resource_name: str, current_value_fn: Callable[[dict[str, Any]], int]) -> Callable[..., Any]:
    async def dependency(
        entitlements: Annotated[dict[str, Any], Depends(get_entitlements_dependency)],
    ) -> dict[str, Any]:
        _assert_quota(entitlements, resource_name, current_value_fn(entitlements))
        return entitlements

    return dependency
