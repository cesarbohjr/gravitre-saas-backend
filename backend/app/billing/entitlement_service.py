"""Single source of truth for org billing access (trial expiry, subscription state)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from supabase import Client

from app.auth.dependencies import get_org_context
from app.billing.service import get_org_billing, get_supabase_client, normalize_plan_code
from app.config import Settings, get_settings

PLAN_REQUIRED_ERROR = "plan_required"
UPGRADE_URL = "/settings/billing"

# Paths that remain reachable when billing is blocked (user must be able to upgrade).
BILLING_GATE_ALLOWED_PREFIXES: tuple[str, ...] = (
    "/health",
    "/api/auth",
    "/api/billing",
    "/api/onboarding",
    "/api/webhooks",
    "/api/internal",
    "/api/entitlements",
    "/api/settings",
    "/api/org",
    "/api/platform",
)

# Product usage paths blocked when trial expired / subscription inactive.
BILLING_GATE_BLOCKED_PREFIXES: tuple[str, ...] = (
    "/api/agent-jobs",
    "/api/agent-swarm",
    "/api/agents/",
    "/api/assistant",
    "/api/chat",
    "/api/connectors/oauth/",
    "/api/conversations",
    "/api/execution",
    "/api/lite",
    "/api/marketplace/",
    "/api/meson",
    "/api/operators/sessions",
    "/api/rag",
    "/api/runs",
    "/api/sessions",
    "/api/sources",
    "/api/workflows/execute",
    "/api/workflows/dry-run",
    "/api/workflows/digital-twin",
    "/api/workflows/from-goal",
)


def _parse_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_trial_ends_at(client: Client, org_id: str, billing: dict[str, Any]) -> datetime | None:
    trial_ends_at = _parse_iso_datetime(billing.get("current_period_end"))
    if trial_ends_at:
        return trial_ends_at
    org_row = (
        client.table("organizations")
        .select("settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not org_row:
        return None
    settings = org_row[0].get("settings") or {}
    billing_settings = settings.get("billing") if isinstance(settings, dict) else {}
    if isinstance(billing_settings, dict):
        return _parse_iso_datetime(billing_settings.get("trial_ends_at"))
    return None


def _is_sandbox_exempt(client: Client, org_id: str) -> bool:
    org_row = (
        client.table("organizations")
        .select("settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not org_row:
        return False
    settings = org_row[0].get("settings") or {}
    if not isinstance(settings, dict):
        return False
    billing_settings = settings.get("billing") or {}
    if isinstance(billing_settings, dict) and billing_settings.get("sandbox_exempt"):
        return True
    marketplace = settings.get("marketplace") or {}
    return isinstance(marketplace, dict) and bool(marketplace.get("sandbox"))


def resolve_billing_state(
    *,
    billing_row: dict[str, Any] | None,
    trial_ends_at: datetime | None,
    sandbox_exempt: bool = False,
) -> dict[str, Any]:
    """Compute authoritative billing state for an org."""
    now = datetime.now(timezone.utc)
    billing = billing_row or {}
    raw_status = str(billing.get("billing_status") or "trialing").strip().lower()
    if raw_status == "canceled":
        raw_status = "cancelled"

    plan_code = normalize_plan_code(billing.get("plan_code") or "node")
    status = raw_status
    days_remaining: int | None = None

    if trial_ends_at:
        delta = trial_ends_at - now
        days_remaining = max(0, int(delta.total_seconds() // 86400))

    if sandbox_exempt or raw_status == "active":
        return {
            "plan": plan_code,
            "status": "active" if sandbox_exempt else status,
            "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
            "is_blocked": False,
            "days_remaining_in_trial": days_remaining,
        }

    if raw_status == "trialing" and trial_ends_at and trial_ends_at <= now:
        return {
            "plan": plan_code,
            "status": "trial_expired",
            "trial_ends_at": trial_ends_at.isoformat(),
            "is_blocked": True,
            "days_remaining_in_trial": 0,
        }

    if raw_status in {"cancelled", "canceled"}:
        return {
            "plan": plan_code,
            "status": "canceled",
            "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
            "is_blocked": True,
            "days_remaining_in_trial": days_remaining,
        }

    if raw_status == "past_due":
        return {
            "plan": plan_code,
            "status": "past_due",
            "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
            "is_blocked": True,
            "days_remaining_in_trial": days_remaining,
        }

    return {
        "plan": plan_code,
        "status": status if status != "trialing" else "trialing",
        "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
        "is_blocked": False,
        "days_remaining_in_trial": days_remaining,
    }


def get_org_billing_state(client: Client, org_id: str) -> dict[str, Any]:
    billing = get_org_billing(client, org_id) or {
        "plan_code": "node",
        "billing_status": "trialing",
    }
    trial_ends_at = _load_trial_ends_at(client, org_id, billing)
    sandbox_exempt = _is_sandbox_exempt(client, org_id)
    return resolve_billing_state(
        billing_row=billing,
        trial_ends_at=trial_ends_at,
        sandbox_exempt=sandbox_exempt,
    )


class PlanRequiredError(HTTPException):
    """402 — subscription/trial required; structured for frontend upgrade UX."""

    def __init__(self, subscription_status: str, upgrade_url: str = UPGRADE_URL) -> None:
        message = (
            "Your 7-day trial has ended. Upgrade to continue using Gravitre."
            if subscription_status == "trial_expired"
            else "An active subscription is required to continue using Gravitre."
        )
        super().__init__(
            status_code=402,
            detail={
                "error": PLAN_REQUIRED_ERROR,
                "subscription_status": subscription_status,
                "message": message,
                "upgrade_url": upgrade_url,
            },
        )


class PlanLimitExceededError(HTTPException):
    """402 — plan resource limit reached; same shape for every resource type."""

    def __init__(
        self,
        limit_type: str,
        current: int,
        max_allowed: int,
        upgrade_url: str = UPGRADE_URL,
    ) -> None:
        super().__init__(
            status_code=402,
            detail={
                "error": "plan_limit_exceeded",
                "limit_type": limit_type,
                "current": current,
                "max": max_allowed,
                "upgrade_url": upgrade_url,
            },
        )


def assert_org_not_blocked(client: Client, org_id: str) -> dict[str, Any]:
    state = get_org_billing_state(client, org_id)
    if state["is_blocked"]:
        raise PlanRequiredError(str(state["status"]))
    return state


def should_gate_path(path: str) -> bool:
    if not path.startswith("/api/"):
        return False
    for prefix in BILLING_GATE_ALLOWED_PREFIXES:
        if path.startswith(prefix):
            return False
    for prefix in BILLING_GATE_BLOCKED_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


async def require_active_plan(
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """FastAPI dependency — block plan-gated routes when trial expired or unpaid."""
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    assert_org_not_blocked(client, org_id)
