from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
from typing import Any

from fastapi import HTTPException, status
from supabase import Client, create_client

from app.config import Settings
from app.core.errors import error_detail

DEFAULT_PLAN_CODE = "node"

PLAN_CODE_ALIASES: dict[str, str] = {
    "starter": "node",
    "growth": "control",
    "scale": "command",
    "enterprise": "command",
}

DEFAULT_PLANS: dict[str, dict[str, Any]] = {
    "node": {
        "code": "node",
        "name": "Node",
        "price_usd": 49,
        "agents_limit": 3,
        "workflows_limit": 10,
        "environments_limit": 1,
        "ai_credits_included": 2000,
        "workflow_runs_included": 1000,
        "features": {
            "approvals": False,
            "audit_logs": False,
            "versioning": False,
            "advanced_connectors": False,
        },
        "overage_rates": {"ai_credit": 0.02, "workflow_runs_per_1000": 10},
    },
    "control": {
        "code": "control",
        "name": "Control",
        "price_usd": 129,
        "agents_limit": 15,
        "workflows_limit": 50,
        "environments_limit": 2,
        "ai_credits_included": 15000,
        "workflow_runs_included": 10000,
        "features": {
            "approvals": True,
            "audit_logs": "basic",
            "versioning": True,
            "advanced_connectors": False,
        },
        "overage_rates": {"ai_credit": 0.015, "workflow_runs_per_1000": 8},
    },
    "command": {
        "code": "command",
        "name": "Command",
        "price_usd": 299,
        "agents_limit": 50,
        "workflows_limit": None,
        "environments_limit": 5,
        "ai_credits_included": 75000,
        "workflow_runs_included": 50000,
        "features": {
            "approvals": "advanced",
            "audit_logs": "full",
            "versioning": "full",
            "advanced_connectors": True,
            "rbac": True,
        },
        "overage_rates": {"ai_credit": 0.012, "workflow_runs_per_1000": 5},
    },
    "enterprise": {
        "code": "enterprise",
        "name": "Enterprise",
        "price_usd": None,
        "agents_limit": None,
        "workflows_limit": None,
        "environments_limit": None,
        "ai_credits_included": 0,
        "workflow_runs_included": 0,
        "features": {
            "approvals": "custom",
            "audit_logs": "custom",
            "versioning": "custom",
            "advanced_connectors": True,
            "rbac": True,
        },
        "overage_rates": {},
    },
}

ADVANCED_CONNECTORS = {"salesforce", "hubspot", "microsoft365", "stripe"}

USAGE_DEFAULTS = {
    "ai_credits": 1,
    "workflow_runs": 1,
    "operator_usage": 1,
    "rag_usage": 1,
}

TOKENS_PER_CREDIT = 1000
MODEL_MULTIPLIERS: list[tuple[str, float]] = [
    ("gpt-4o", 2.0),
    ("gpt-4", 2.5),
    ("gpt-3.5", 1.0),
    ("text-embedding", 0.2),
]


def get_supabase_client(settings: Settings) -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_billing_plans(client: Client) -> dict[str, dict[str, Any]]:
    rows = client.table("billing_plans").select("*").execute().data or []
    if not rows:
        return DEFAULT_PLANS
    plans = {row["code"]: row for row in rows if row.get("code")}
    if not plans:
        return DEFAULT_PLANS
    return plans


def normalize_plan_code(plan_code: str | None) -> str:
    code = (plan_code or DEFAULT_PLAN_CODE).strip().lower()
    return PLAN_CODE_ALIASES.get(code, code)


def _resolve_plan(plans: dict[str, dict[str, Any]], plan_code: str) -> dict[str, Any] | None:
    if plan_code in plans:
        return plans[plan_code]
    if plan_code == "node":
        return plans.get("starter")
    if plan_code == "control":
        return plans.get("growth")
    if plan_code == "command":
        return plans.get("scale") or plans.get("enterprise")
    return None


def get_plan_for_org(client: Client, org_id: str) -> dict[str, Any]:
    base_plan = get_base_plan_for_org(client, org_id)
    overrides = get_org_billing_overrides(client, org_id)
    return apply_overrides(base_plan, overrides)


def get_org_billing(client: Client, org_id: str) -> dict | None:
    row = (
        client.table("org_billing")
        .select("*")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
    )
    if not row:
        return None
    return dict(row[0])


def get_org_billing_overrides(client: Client, org_id: str) -> dict | None:
    row = (
        client.table("org_billing_overrides")
        .select("*")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
    )
    if not row:
        return None
    return dict(row[0])


def overrides_active(overrides: dict | None) -> bool:
    if not overrides:
        return False
    for key in (
        "agents_limit",
        "workflows_limit",
        "environments_limit",
        "ai_credits_included",
        "workflow_runs_included",
        "approvals",
        "audit_logs",
        "versioning",
        "advanced_connectors",
        "rbac",
    ):
        if overrides.get(key) is not None:
            return True
    return False


def apply_overrides(plan: dict[str, Any], overrides: dict | None) -> dict[str, Any]:
    if not overrides:
        return plan
    merged = {**plan}
    for key in (
        "agents_limit",
        "workflows_limit",
        "environments_limit",
        "ai_credits_included",
        "workflow_runs_included",
    ):
        if overrides.get(key) is not None:
            merged[key] = overrides.get(key)
    features = dict(merged.get("features") or {})
    for feature_key in ("approvals", "audit_logs", "versioning", "advanced_connectors", "rbac"):
        if overrides.get(feature_key) is not None:
            features[feature_key] = overrides.get(feature_key)
    merged["features"] = features
    return merged


def get_base_plan_for_org(client: Client, org_id: str) -> dict[str, Any]:
    plans = get_billing_plans(client)
    billing = get_org_billing(client, org_id)
    plan_code = normalize_plan_code(billing.get("plan_code") if billing else DEFAULT_PLAN_CODE)
    resolved = _resolve_plan(plans, plan_code)
    if resolved:
        return resolved
    fallback = _resolve_plan(DEFAULT_PLANS, DEFAULT_PLAN_CODE)
    return fallback or next(iter(DEFAULT_PLANS.values()))


def get_or_create_org_billing(client: Client, org_id: str) -> dict:
    existing = get_org_billing(client, org_id)
    if existing:
        return existing
    created = client.table("org_billing").insert(
        {"org_id": org_id, "plan_code": DEFAULT_PLAN_CODE, "billing_status": "trialing"}
    ).execute()
    if not created.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("Billing record create failed", "VALIDATION_ERROR"),
        )
    return dict(created.data[0])


def get_current_period(now: datetime | None = None) -> tuple[date, date]:
    current = now or datetime.now(timezone.utc)
    period_start = date(current.year, current.month, 1)
    if current.month == 12:
        next_month = date(current.year + 1, 1, 1)
    else:
        next_month = date(current.year, current.month + 1, 1)
    period_end = next_month - timedelta(days=1)
    return period_start, period_end


def _sum_usage(
    client: Client,
    org_id: str,
    metric_type: str,
    period_start: date,
    period_end: date,
    environment: str | None = None,
) -> int:
    q = (
        client.table("usage_tracking")
        .select("quantity")
        .eq("org_id", org_id)
        .eq("metric_type", metric_type)
        .eq("period_start", period_start.isoformat())
        .eq("period_end", period_end.isoformat())
    )
    if environment:
        q = q.eq("environment", environment)
    rows = q.execute().data or []
    return sum(int(row.get("quantity") or 0) for row in rows)


def get_usage_totals(
    client: Client,
    org_id: str,
    period_start: date,
    period_end: date,
    environment: str | None = None,
) -> dict[str, int]:
    totals: dict[str, int] = {}
    for metric in ("ai_credits", "workflow_runs", "operator_usage", "rag_usage"):
        totals[metric] = _sum_usage(client, org_id, metric, period_start, period_end, environment)
    return totals


def record_usage(
    client: Client,
    org_id: str,
    environment: str,
    metric_type: str,
    quantity: int,
    period_start: date,
    period_end: date,
    metadata: dict[str, Any] | None = None,
) -> None:
    if quantity == 0:
        return
    payload: dict[str, Any] = {
        "org_id": org_id,
        "environment": environment,
        "metric_type": metric_type,
        "quantity": quantity,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }
    if metadata:
        payload["model_name"] = metadata.get("model_name")
        payload["input_tokens"] = metadata.get("input_tokens")
        payload["output_tokens"] = metadata.get("output_tokens")
        payload["credits"] = metadata.get("credits")
        payload["source"] = metadata.get("source")
        payload["source_id"] = metadata.get("source_id")
    client.table("usage_tracking").insert(payload).execute()


def record_overage(
    client: Client,
    org_id: str,
    environment: str,
    metric_type: str,
    quantity: int,
    period_start: date,
    period_end: date,
) -> None:
    if quantity <= 0:
        return
    client.table("overage_usage").insert(
        {
            "org_id": org_id,
            "environment": environment,
            "metric_type": metric_type,
            "quantity": quantity,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }
    ).execute()


def apply_usage_with_overage(
    client: Client,
    org_id: str,
    environment: str,
    metric_type: str,
    quantity: int,
    plan: dict[str, Any],
    period_start: date,
    period_end: date,
    metadata: dict[str, Any] | None = None,
) -> None:
    if quantity <= 0:
        return
    total_before = _sum_usage(client, org_id, metric_type, period_start, period_end, environment)
    record_usage(client, org_id, environment, metric_type, quantity, period_start, period_end, metadata=metadata)
    total_after = total_before + quantity
    included = 0
    if metric_type == "ai_credits":
        included = int(plan.get("ai_credits_included") or 0)
    if metric_type == "workflow_runs":
        included = int(plan.get("workflow_runs_included") or 0)
    if included <= 0:
        return
    if total_before >= included:
        record_overage(client, org_id, environment, metric_type, quantity, period_start, period_end)
    elif total_after > included:
        record_overage(client, org_id, environment, metric_type, total_after - included, period_start, period_end)


def require_feature(plan: dict[str, Any], feature: str) -> None:
    features = plan.get("features") or {}
    value = features.get(feature)
    if not value or value is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Upgrade required", "UNAUTHORIZED", {"feature": feature}),
        )


def require_limit(current_count: int, limit: int | None, label: str) -> None:
    if limit is None:
        return
    if current_count >= limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Plan limit reached", "VALIDATION_ERROR", {"limit": label}),
        )


def usage_warning(used: int, included: int) -> dict[str, Any]:
    if included <= 0:
        return {"percent": 0, "warning": False, "overage": 0}
    percent = round((used / included) * 100, 2)
    warning = percent >= 80
    overage = max(used - included, 0)
    return {"percent": percent, "warning": warning, "overage": overage}


def get_default_usage_quantity(metric_type: str) -> int:
    return int(USAGE_DEFAULTS.get(metric_type, 1))


def estimate_tokens(text: str | None) -> int:
    if not text:
        return 0
    chars = len(text)
    if chars <= 0:
        return 0
    return max(1, math.ceil(chars / 4))


def model_multiplier(model_name: str | None) -> float:
    if not model_name:
        return 1.0
    name = model_name.lower()
    for needle, multiplier in MODEL_MULTIPLIERS:
        if needle in name:
            return multiplier
    return 1.0


def compute_ai_credits(input_tokens: int, output_tokens: int, model_name: str | None = None) -> int:
    total = max(input_tokens, 0) + max(output_tokens, 0)
    if total <= 0:
        return 0
    multiplier = model_multiplier(model_name)
    credits = math.ceil((total / TOKENS_PER_CREDIT) * multiplier)
    return max(1, int(credits))


def build_ai_usage_metadata(
    input_texts: list[str],
    output_texts: list[str],
    model_name: str | None,
    source: str,
    source_id: str | None,
) -> dict[str, Any]:
    input_tokens = sum(estimate_tokens(text) for text in input_texts if text)
    output_tokens = sum(estimate_tokens(text) for text in output_texts if text)
    credits = compute_ai_credits(input_tokens, output_tokens, model_name)
    if credits <= 0:
        credits = get_default_usage_quantity("ai_credits")
    return {
        "model_name": model_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "credits": credits,
        "source": source,
        "source_id": source_id,
    }
