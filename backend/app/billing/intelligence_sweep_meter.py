"""Subscription-gated Intelligence Overview sweep unit reservation/settlement.

Authoritative access comes from the existing org billing state and effective
plan; all quota admission is serialized by the database, never application
read-count-then-write. Offline tests inject a fake database.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException


def entitled_sweep_limit(client: Any, org_id: str) -> tuple[str, int]:
    from app.billing.service import get_org_billing, get_plan_for_org
    from app.billing.entitlement_service import (
        resolve_billing_state, _load_trial_ends_at, _is_sandbox_exempt,
    )
    billing = get_org_billing(client, org_id)
    if not billing:
        raise HTTPException(status_code=402, detail="An active subscription is required")
    state = resolve_billing_state(
        billing_row=billing,
        trial_ends_at=_load_trial_ends_at(client, org_id, billing),
        sandbox_exempt=_is_sandbox_exempt(client, org_id),
    )
    if state["is_blocked"]:
        raise HTTPException(status_code=402, detail="Subscription inactive")
    plan = get_plan_for_org(client, org_id, billing=billing)
    features = plan.get("features") or {}
    # Absent feature is DENIED, not an unmetered free allowance.
    plan_code = str(plan.get("code") or state.get("plan") or "").lower()
    # Explicit default allowances for existing plans whose stored feature JSON
    # predates the Intelligence Overview rollout. Org overrides still win.
    baseline = {"node": 5, "control": 25, "command": 100}
    limit = features.get("intelligence_sweeps_per_month", baseline.get(plan_code))
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise HTTPException(status_code=402, detail="Intelligence sweep entitlement unavailable")
    if limit > 100000:
        raise HTTPException(status_code=503, detail="Invalid plan entitlement configuration")
    # Calendar period is a deterministic reconciliation partition; future
    # pricing can use a subscription-cycle key without changing ledger schema.
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    return period, limit


def reserve_sweep(client: Any, org_id: str, actor_id: str | None, scope: dict[str, Any]) -> dict:
    period, limit = entitled_sweep_limit(client, org_id)
    try:
        response = client.rpc("admit_metered_intelligence_sweep", {
            "p_org_id": org_id, "p_requested_by": actor_id,
            "p_scope": scope, "p_period": period, "p_limit": limit,
        }).execute()
    except Exception as exc:
        if "intelligence sweep entitlement exceeded" in str(exc):
            raise HTTPException(status_code=402, detail="Monthly intelligence sweep quota exhausted") from exc
        raise HTTPException(status_code=503, detail="Atomic sweep admission unavailable") from exc
    payload = response.data
    row = payload[0] if isinstance(payload, list) and payload else payload if isinstance(payload, dict) else None
    if not isinstance(row, dict) or not row.get("id"):
        raise HTTPException(status_code=503, detail="Atomic sweep admission unavailable")
    return row


def settle_sweep(client: Any, org_id: str, sweep_id: str, *, consumed: bool = True) -> bool:
    """Returns false for an already-settled ledger; never double-counts usage."""
    response = client.rpc("settle_intelligence_sweep_unit", {
        "p_org_id": org_id, "p_sweep_id": sweep_id,
        "p_state": "settled" if consumed else "released",
    }).execute()
    return response.data is True


def sweep_usage_snapshot(client: Any, org_id: str) -> dict[str, Any]:
    """Read-only usage display from the authoritative reservation ledger.

    Counts in-flight reservations, not merely already-settled work.
    The atomic admission RPC remains authoritative under concurrency.
    """
    period, limit = entitled_sweep_limit(client, org_id)
    rows = (client.table("intelligence_sweep_usage_ledger")
            .select("units,state").eq("org_id", org_id)
            .eq("subscription_period", period)
            .in_("state", ["reserved", "settled"]).limit(100001).execute()).data or []
    used = sum(int(row.get("units") or 0) for row in rows)
    return {"period": period, "limit": limit, "used": used,
            "remaining": max(limit - used, 0),
            "unit": "intelligence_sweep",
            "source": "atomic_usage_ledger",
            "admission_authority": "admit_metered_intelligence_sweep"}
