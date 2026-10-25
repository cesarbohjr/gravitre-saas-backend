"""Reconcile uncertain provider charges using verified provider evidence.

Never automatically release timeout reservations: the provider might have charged.
Only a verified source-of-record outcome allows settlement.
"""
from __future__ import annotations
from typing import Any

def reconcile_reserved_credit(
    client: Any, *, org_id: str, provider: str, request_id: str,
    confirmed_consumed: int | None, provider_evidence_id: str,
    verified_by: str,
) -> bool:
    if not all((org_id, provider, request_id, provider_evidence_id, verified_by)):
        raise ValueError("Tenant, provider, request, verified evidence and operator required")
    if confirmed_consumed not in (0, 1):
        raise ValueError("Use only verified 0 or 1 unit outcomes; other amounts require dedicated provider mapping")
    # Read the tenant record first: disallow cross-tenant identifiers.
    rows=(client.table("prospect_provider_usage").select("id,status,credits_reserved")
          .eq("org_id",org_id).eq("provider",provider).eq("request_id",request_id)
          .limit(1).execute().data or [])
    if not rows or rows[0].get("status")!="reserved":
        return False
    if confirmed_consumed>int(rows[0].get("credits_reserved") or 0):
        return False
    state="charged" if confirmed_consumed else "released"
    result=client.rpc("prospect_settle_credits",{
        "p_org":org_id,"p_provider":provider,"p_request":request_id,
        "p_consumed":confirmed_consumed,"p_status":state
    }).execute()
    # Provider evidence must also be recorded in the immutable audit system
    # by the caller; do not silently declare vendor charge truth.
    return result.data is True
