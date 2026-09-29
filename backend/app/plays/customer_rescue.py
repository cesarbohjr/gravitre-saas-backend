"""Customer Rescue observe/recommend projection over existing churn advisory.

No contact or connector WRITE is performed here.
"""
from __future__ import annotations

from typing import Any

from app.services.churn_advisory_service import build_churn_advisory_cards


async def observe_customer_rescue(
    org_id: str,
    *,
    settings: Any,
    client: Any,
    limit: int = 25,
) -> dict[str, Any]:
    payload = await build_churn_advisory_cards(
        org_id,
        settings=settings,
        client=client,
        limit=limit,
    )
    recommendations: list[dict[str, Any]] = []
    for card in payload.get("recommendations") or []:
        evidence = card.get("evidence") if isinstance(card.get("evidence"), dict) else {}
        recommendations.append(
            {
                "id": card.get("id"),
                "signalType": card.get("kind"),
                "customerId": evidence.get("customerId"),
                "status": "RECOMMENDED",
                "title": card.get("title"),
                "recommendation": card.get("reason"),
                "evidence": evidence,
                "advisoryOnly": True,
                "actionTaken": False,
                "businessResult": {
                    "verified": False,
                    "retainedRevenue": None,
                    "churnAvoided": None,
                    "reason": "Churn risk or an intervention recommendation is not proof that churn was avoided.",
                },
            }
        )
    return {
        "mode": "OBSERVE",
        "signals": recommendations,
        "count": len(recommendations),
        "gate": payload.get("gate"),
        "modelTrained": bool(payload.get("trained")),
        "actionTaken": False,
        "truthRule": (
            "Customer Rescue remains advisory until a governed action is taken and "
            "retention is verified from a source of record."
        ),
    }
