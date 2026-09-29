"""Revenue Recovery read model over existing evidence-backed signals.

This module performs no connector WRITE and creates no new signal store. It
projects existing optimization_suggestions that were generated from canonical
finance/CRM evidence.
"""
from __future__ import annotations

from typing import Any

REVENUE_RECOVERY_SIGNAL_TYPES = frozenset({"overdue_invoice", "stalled_deal"})


def _money_sample(evidence: dict[str, Any]) -> dict[str, Any] | None:
    invoices = evidence.get("sample_invoices")
    if not isinstance(invoices, list):
        return None
    balances: list[float] = []
    for row in invoices:
        if not isinstance(row, dict):
            continue
        try:
            balances.append(float(row.get("balance") or 0))
        except (TypeError, ValueError):
            continue
    if not balances:
        return None
    return {
        "sampleOpenBalance": round(sum(balances), 2),
        "sampleSize": len(balances),
        "scope": "sample_only",
        "verifiedRevenueRecovered": None,
    }


def project_revenue_recovery_signal(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    suggestion_type = str(row.get("suggestion_type") or "")
    return {
        "id": str(row.get("id") or ""),
        "signalType": suggestion_type,
        "entityType": row.get("target_entity_type"),
        "entityId": row.get("target_entity_id"),
        "status": "RECOMMENDED",
        "source": evidence.get("source"),
        "evidence": evidence,
        "recommendation": row.get("suggested_action"),
        "estimatedImpact": row.get("estimated_impact"),
        "sampleFinancials": _money_sample(evidence),
        "businessResult": {
            "verified": False,
            "recoveredRevenue": None,
            "reason": "A detected or recommended opportunity is not recovered revenue.",
        },
        "createdAt": row.get("created_at"),
    }


def list_revenue_recovery_signals(
    client: Any,
    org_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = (
        client.table("optimization_suggestions")
        .select(
            "id, org_id, target_entity_type, target_entity_id, suggestion_type, "
            "evidence, suggested_action, estimated_impact, status, created_at"
        )
        .eq("org_id", org_id)
        .eq("status", "pending_review")
        .order("created_at", desc=True)
        .limit(max(1, min(int(limit), 200)))
        .execute()
        .data
        or []
    )
    return [
        project_revenue_recovery_signal(row)
        for row in rows
        if str(row.get("suggestion_type") or "") in REVENUE_RECOVERY_SIGNAL_TYPES
    ]
