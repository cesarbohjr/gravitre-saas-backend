from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
import uuid
from typing import Any

from fastapi import HTTPException, status
from supabase import Client, create_client

from app.config import Settings
from app.core.errors import error_detail
from app.core.logging import get_logger

logger = get_logger(__name__)

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
        "agents_limit": 1,
        "workflows_limit": 10,
        "environments_limit": 1,
        "ai_credits_included": 1000,
        "workflow_runs_included": 500,
        "features": {
            "outputs_per_month": 10,
            "core_users": 1,
            "lite_users": 2,
            "research_lookups_per_month": 10,
            "meson": False,
            "email_delivery": True,
            "basic_campaigns": True,
            "integrations": 3,
            "support": "community",
            "approvals": True,
            "audit_logs": "basic",
            "versioning": False,
            "advanced_connectors": True,
        },
        "overage_rates": {"output": 2.50, "meson": None, "research_lookup": 0.35},
    },
    "control": {
        "code": "control",
        "name": "Control",
        "price_usd": 129,
        "agents_limit": 3,
        "workflows_limit": 40,
        "environments_limit": 2,
        "ai_credits_included": 5000,
        "workflow_runs_included": 2500,
        "features": {
            "outputs_per_month": 40,
            "core_users": 2,
            "lite_users": 5,
            "research_lookups_per_month": 60,
            "meson": 10,
            "crm_integration": True,
            "outlook_integration": True,
            "multi_step_execution": True,
            "full_campaigns": True,
            "slack_delivery": True,
            "support": "priority",
            "approvals": True,
            "audit_logs": "basic",
            "versioning": True,
            "advanced_connectors": True,
        },
        "overage_rates": {"output": 2.00, "meson": 3.00, "research_lookup": 0.35},
    },
    "command": {
        "code": "command",
        "name": "Command",
        "price_usd": 299,
        "agents_limit": 8,
        "workflows_limit": 120,
        "environments_limit": 5,
        "ai_credits_included": 15000,
        "workflow_runs_included": 10000,
        "features": {
            "outputs_per_month": 120,
            "core_users": 5,
            "lite_users": -1,
            "research_lookups_per_month": 200,
            "meson": 40,
            "approvals": True,
            "advanced_integrations": True,
            "team_workspace": True,
            "cross_department_agents": True,
            "custom_agent_training": True,
            "support": "dedicated",
            "audit_logs": "full",
            "versioning": "full",
            "advanced_connectors": True,
            "rbac": True,
        },
        "overage_rates": {"output": 1.50, "meson": 2.00, "research_lookup": 0.35},
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
            "outputs_per_month": -1,
            "core_users": -1,
            "lite_users": -1,
            "meson": -1,
            "research_lookups_per_month": 200,
            "custom": True,
            "sla": True,
            "dedicated_support": True,
            "sso": True,
            "audit_logs": True,
            "approvals": "custom",
            "versioning": "custom",
            "advanced_connectors": True,
            "rbac": True,
        },
        "overage_rates": {"research_lookup": 0.35},
    },
}

# CRM connectors (HubSpot, Salesforce) are available on all paid tiers; gate only
# enterprise payment/infra connectors behind advanced_connectors.
ADVANCED_CONNECTORS = {"microsoft365", "stripe"}

USAGE_DEFAULTS = {
    "ai_credits": 1,
    "workflow_runs": 1,
    "operator_usage": 1,
    "rag_usage": 1,
}

TOKENS_PER_CREDIT = 1000
# Credit multiplier by model-name substring (first match wins). Keep current
# provider families only; flagship reasoning models cost more credits per token.
MODEL_MULTIPLIERS: list[tuple[str, float]] = [
    ("gpt-5.5", 2.0),
    ("gpt-5.4-mini", 1.0),
    ("gpt-4.1", 1.5),
    ("claude-sonnet", 2.0),
    ("claude-haiku", 1.0),
    ("gemini-2.5-pro", 1.5),
    ("gemini-2.5-flash", 0.5),
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


def _normalize_plan_row(row: dict[str, Any]) -> dict[str, Any]:
    """Merge DB billing_plans rows with code defaults (features JSON is often partial)."""
    code = normalize_plan_code(str(row.get("code") or DEFAULT_PLAN_CODE))
    template = dict(DEFAULT_PLANS.get(code) or DEFAULT_PLANS[DEFAULT_PLAN_CODE])
    merged = {
        **template,
        **{k: v for k, v in row.items() if k not in {"features"} and v is not None},
    }
    template_features = dict(template.get("features") or {})
    db_features = row.get("features") if isinstance(row.get("features"), dict) else {}
    merged["features"] = {**template_features, **db_features}
    return merged


def get_plan_for_org(client: Client, org_id: str) -> dict[str, Any]:
    base_plan = get_base_plan_for_org(client, org_id)
    overrides = get_org_billing_overrides(client, org_id)
    return apply_overrides(base_plan, overrides)


def resolve_org_id_from_checkout_metadata(client: Client, metadata: dict | None) -> str | None:
    """Resolve org_id from Stripe checkout session metadata."""
    meta = metadata or {}
    org_id = str(meta.get("org_id") or "").strip() or None
    if org_id:
        return org_id

    user_id = str(meta.get("user_id") or "").strip() or None
    if user_id:
        member_rows = (
            client.table("organization_members")
            .select("org_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if member_rows:
            return str(member_rows[0]["org_id"])

    checkout_email = str(meta.get("checkout_email") or meta.get("email") or "").strip().lower()
    if checkout_email:
        user_rows = (
            client.table("users")
            .select("org_id")
            .eq("email", checkout_email)
            .limit(1)
            .execute()
            .data
            or []
        )
        if user_rows:
            return str(user_rows[0]["org_id"])

    return None


def resolve_org_id_from_stripe_customer(client: Client, customer_id: str | None) -> str | None:
    """Resolve org_id from a Stripe customer id stored on billing/subscription rows."""
    normalized = str(customer_id or "").strip()
    if not normalized:
        return None
    for table in ("org_billing", "subscriptions"):
        rows = (
            client.table(table)
            .select("org_id")
            .eq("stripe_customer_id", normalized)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows and rows[0].get("org_id"):
            return str(rows[0]["org_id"])
    return None


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


def get_org_hard_budget_override(client: Client, org_id: str) -> bool | None:
    """Per-org hard-budget override from org_billing.hard_budget_enabled.

    Returns True/False to force the gate on/off for this org, or None to inherit
    the global AI_HARD_BUDGET_ENABLED flag. Returns None on any error (e.g. the
    column not yet migrated) so behavior safely falls back to the global flag.
    """
    try:
        rows = (
            client.table("org_billing")
            .select("hard_budget_enabled")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows and rows[0].get("hard_budget_enabled") is not None:
            return bool(rows[0]["hard_budget_enabled"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("hard_budget override lookup failed org_id=%s error=%s", org_id, str(exc))
    return None


def get_org_billing_overrides(client: Client, org_id: str) -> dict | None:
    try:
        row = (
            client.table("org_billing_overrides")
            .select("*")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if "org_billing_overrides" in message or "pgrst205" in message:
            logger.warning("org_billing_overrides lookup skipped org_id=%s error=%s", org_id, exc)
            return None
        raise
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
        return _normalize_plan_row(resolved)
    # Prefer the org's plan code from in-code defaults when billing_plans is incomplete.
    fallback = _resolve_plan(DEFAULT_PLANS, plan_code) or _resolve_plan(DEFAULT_PLANS, DEFAULT_PLAN_CODE)
    return _normalize_plan_row(fallback or next(iter(DEFAULT_PLANS.values())))


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


def derive_idempotency_key(
    org_id: str,
    metric_type: str,
    period_start: date,
    metadata: dict[str, Any] | None = None,
    suffix: str = "",
) -> str:
    """Build a stable idempotency key for a usage record.

    Uses metadata.source + metadata.source_id when available (e.g.
    "model_call" + the model_calls row id), so re-running the metering for the
    same underlying event is a no-op. Falls back to a random uuid when no
    source_id is present, which preserves the previous always-insert behavior
    for callers that have no stable anchor.
    """
    meta = metadata or {}
    source = str(meta.get("source") or metric_type)
    source_id = meta.get("source_id")
    anchor = str(source_id) if source_id else uuid.uuid4().hex
    key = f"{org_id}:{source}:{anchor}:{period_start.isoformat()}"
    return f"{key}:{suffix}" if suffix else key


def _idempotent_insert(
    client: Client,
    table: str,
    org_id: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> bool:
    """INSERT ... ON CONFLICT (org_id, idempotency_key) DO NOTHING.

    Returns True if a row was inserted, False if it was a duplicate. Falls back
    to a plain insert (still records usage, without dedupe) if the idempotency
    column/index is not present yet — so billing keeps working if the migration
    has not been applied. Returns True for the fallback insert.
    """
    try:
        resp = (
            client.table(table)
            .upsert(
                {**payload, "idempotency_key": idempotency_key},
                on_conflict="org_id,idempotency_key",
                ignore_duplicates=True,
            )
            .execute()
        )
        # With ignore-duplicates, a conflicting row is skipped and not returned.
        return bool(resp.data)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "idempotent insert fallback table=%s org_id=%s error=%s", table, org_id, str(exc)
        )
        client.table(table).insert(payload).execute()
        return True


def record_usage(
    client: Client,
    org_id: str,
    environment: str,
    metric_type: str,
    quantity: int,
    period_start: date,
    period_end: date,
    metadata: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> bool:
    """Record a usage row idempotently. Returns True if inserted, False if it
    was a duplicate (so callers can avoid double-counting downstream)."""
    if quantity == 0:
        return False
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
    key = idempotency_key or derive_idempotency_key(org_id, metric_type, period_start, metadata)
    return _idempotent_insert(client, "usage_tracking", org_id, payload, key)


def record_overage(
    client: Client,
    org_id: str,
    environment: str,
    metric_type: str,
    quantity: int,
    period_start: date,
    period_end: date,
    idempotency_key: str | None = None,
) -> bool:
    if quantity <= 0:
        return False
    payload = {
        "org_id": org_id,
        "environment": environment,
        "metric_type": metric_type,
        "quantity": quantity,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }
    key = idempotency_key or derive_idempotency_key(org_id, metric_type, period_start, suffix="overage")
    return _idempotent_insert(client, "overage_usage", org_id, payload, key)


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
    # Shared idempotency anchor so usage + its overage dedupe together. On a
    # duplicate (retry / re-processed event), record_usage is a no-op and we
    # skip the overage entirely to avoid double-counting.
    base_key = derive_idempotency_key(org_id, metric_type, period_start, metadata)
    total_before = _sum_usage(client, org_id, metric_type, period_start, period_end, environment)
    inserted = record_usage(
        client, org_id, environment, metric_type, quantity, period_start, period_end,
        metadata=metadata, idempotency_key=base_key,
    )
    if not inserted:
        return
    total_after = total_before + quantity
    included = 0
    if metric_type == "ai_credits":
        included = int(plan.get("ai_credits_included") or 0)
    if metric_type == "workflow_runs":
        included = int(plan.get("workflow_runs_included") or 0)
    if included <= 0:
        return
    overage_key = f"{base_key}:overage"
    if total_before >= included:
        record_overage(
            client, org_id, environment, metric_type, quantity, period_start, period_end,
            idempotency_key=overage_key,
        )
    elif total_after > included:
        record_overage(
            client, org_id, environment, metric_type, total_after - included, period_start, period_end,
            idempotency_key=overage_key,
        )


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
        from app.billing.entitlement_service import PlanLimitExceededError

        limit_type = {
            "agents": "agent_count",
            "workflows": "workflow_count",
            "environments": "environment_count",
        }.get(label, label)
        raise PlanLimitExceededError(
            limit_type=limit_type,
            current=current_count,
            max_allowed=int(limit),
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


def build_ai_usage_metadata_from_tokens(
    input_tokens: int,
    output_tokens: int,
    model_name: str | None,
    source: str,
    source_id: str | None,
) -> dict[str, Any]:
    """Build usage metadata from REAL token counts (from the model response),
    rather than char-estimating, so billed credits match model_calls."""
    input_tokens = max(int(input_tokens or 0), 0)
    output_tokens = max(int(output_tokens or 0), 0)
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
