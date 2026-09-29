"""Marketing Performance read model over existing measured marketing signals."""
from __future__ import annotations

from typing import Any

MARKETING_SIGNAL_TYPES = frozenset({"post_publish_marketing_underperformance"})


def project_marketing_signal(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
    return {
        "id": str(row.get("id") or ""),
        "signalType": str(row.get("suggestion_type") or ""),
        "entityType": row.get("target_entity_type"),
        "entityId": row.get("target_entity_id"),
        "status": "RECOMMENDED",
        "source": evidence.get("source"),
        "evidence": evidence,
        "recommendation": row.get("suggested_action"),
        "estimatedImpact": row.get("estimated_impact"),
        "actionTaken": False,
        "businessResult": {
            "verified": False,
            "pipelineInfluenced": None,
            "revenueInfluenced": None,
            "reason": "Post-publish performance movement is not revenue attribution.",
        },
        "createdAt": row.get("created_at"),
    }


def list_marketing_performance_signals(
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
        project_marketing_signal(row)
        for row in rows
        if str(row.get("suggestion_type") or "") in MARKETING_SIGNAL_TYPES
    ]
