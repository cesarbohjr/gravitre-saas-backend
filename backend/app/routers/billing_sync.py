"""Stripe usage-sync endpoints.

- POST /api/internal/billing/sync-usage  — cron-triggered; reports usage for all
  active orgs. Protected by the INTERNAL_API_SECRET shared secret (X-Internal-Secret
  header), NOT a user JWT, so an external scheduler (e.g. Railway cron) can call it.
- POST /api/admin/billing/sync-usage     — admin-only manual trigger for one org,
  with dry_run support for testing.
"""
from __future__ import annotations

import hmac
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import require_admin
from app.billing.service import get_current_period, get_supabase_client
from app.billing.stripe_metering import report_usage_for_active_orgs, report_usage_to_stripe
from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

internal_router = APIRouter(prefix="/api/internal/billing", tags=["billing-internal"])
admin_router = APIRouter(prefix="/api/admin/billing", tags=["billing-admin"])


async def require_internal_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> None:
    secret = (settings.internal_api_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_SECRET is not configured",
        )
    if not x_internal_secret or not hmac.compare_digest(x_internal_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret")


class AdminSyncRequest(BaseModel):
    org_id: str | None = None
    dry_run: bool = True


class BudgetEnforcementRequest(BaseModel):
    # org_id defaults to the admin's own org; if provided it must match it.
    org_id: str | None = None
    # required: true = force gate on, false = force off, null = clear (inherit global).
    enabled: bool | None


class InternalBudgetEnforcementRequest(BaseModel):
    # Platform/cron endpoint can target any org, so org_id is required.
    org_id: str
    enabled: bool | None


def _set_hard_budget_override(settings: Settings, org_id: str, enabled: bool | None) -> dict[str, Any]:
    """Upsert org_billing.hard_budget_enabled. Upsert (not get_or_create) avoids
    the billing_plans FK path; on insert plan_code stays null + billing_status
    uses its default."""
    client = get_supabase_client(settings)
    client.table("org_billing").upsert(
        {
            "org_id": org_id,
            "hard_budget_enabled": enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="org_id",
    ).execute()
    logger.info("budget enforcement override org_id=%s enabled=%s", org_id, enabled)
    return {"org_id": org_id, "hard_budget_enabled": enabled}


@internal_router.post("/sync-usage")
async def sync_usage_cron(
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[None, Depends(require_internal_secret)],
) -> dict[str, Any]:
    """Report metered usage for all active orgs for the current period."""
    period_start, period_end = get_current_period()
    summary = report_usage_for_active_orgs(period_start, period_end, settings)
    logger.info(
        "billing usage sync orgs=%s reported_rows=%s",
        summary.get("orgs"),
        summary.get("reported_rows"),
    )
    return summary


@admin_router.post("/sync-usage")
async def sync_usage_admin(
    body: AdminSyncRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Manual trigger for a single org. dry_run=True (default) calculates without
    calling Stripe."""
    _user, admin_org_id = admin
    org_id = (body.org_id or admin_org_id or "").strip()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id is required")
    if org_id != admin_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only sync usage for your own organization",
        )
    period_start, period_end = get_current_period()
    return report_usage_to_stripe(
        org_id, period_start, period_end, settings, dry_run=body.dry_run
    )


@admin_router.post("/budget-enforcement")
async def set_budget_enforcement(
    body: BudgetEnforcementRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Set the per-org hard-budget override (org_billing.hard_budget_enabled).

    enabled=true forces the budget gate on for this org even when the global
    flag is off; false forces it off; null clears the override (inherit global).
    Scoped to the admin's own org for tenant isolation.
    """
    _user, admin_org_id = admin
    org_id = (body.org_id or admin_org_id or "").strip()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id is required")
    if org_id != admin_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage budget enforcement for your own organization",
        )
    return _set_hard_budget_override(settings, org_id, body.enabled)


@internal_router.post("/budget-enforcement")
async def set_budget_enforcement_internal(
    body: InternalBudgetEnforcementRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[None, Depends(require_internal_secret)],
) -> dict[str, Any]:
    """Platform-wide per-org budget override for ops/cron (any org). Protected by
    INTERNAL_API_SECRET, not a user JWT."""
    org_id = (body.org_id or "").strip()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id is required")
    return _set_hard_budget_override(settings, org_id, body.enabled)
