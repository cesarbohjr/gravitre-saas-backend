"""Suggest-only churn risk cards for CS / Intelligence — never auto-contacts."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.churn_feature_ingest import (
    list_churn_training_rows,
    training_gate_status,
)
from app.ml.churn_scoring import ChurnRiskScorer
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

# Explicit ban — advisory surface must never invoke these.
_FORBIDDEN_ACTIONS = (
    "execute_plan",
    "invoke_tool",
    "send_email",
    "send_slack",
    "auto_contact",
)


def _card(
    *,
    customer_id: str,
    prediction: dict[str, Any],
) -> dict[str, Any]:
    risk = float(prediction.get("risk_score") or 0.0)
    level = str(prediction.get("risk_level") or "unknown")
    return {
        "id": f"churn-advisory-{customer_id}",
        "kind": "churn_risk_advisory",
        "title": f"Account {customer_id}: {level} churn risk",
        "reason": str(prediction.get("recommended_action") or "Review with a human."),
        "evidence": {
            "customerId": customer_id,
            "riskScore": risk,
            "riskLevel": level,
            "contributingFactors": list(prediction.get("contributing_factors") or []),
            "confidence": prediction.get("confidence"),
        },
        "href": "/intelligence/predictive",
        "advisory_only": True,
        "executable": False,
        # No invocation payload — STA-314 style.
    }


async def build_churn_advisory_cards(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Score stored customer feature rows; return suggest-only cards."""
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    gate = training_gate_status(db, org_id)
    rows = list_churn_training_rows(db, org_id)

    # Prefer org-trained artifact; fall back to in-memory untrained structured response.
    scorer = ChurnRiskScorer()
    trained = False
    try:
        from app.ml.model_catalog import load_org_trained_catalog_model

        loaded = await load_org_trained_catalog_model(org_id, "churn_risk_scorer", settings=active)
        if loaded is not None and getattr(loaded, "_model", None) is not None:
            scorer = loaded
            trained = True
    except Exception as exc:  # noqa: BLE001
        logger.debug("churn_advisory_load_model_skipped org_id=%s err=%s", org_id, exc)

    cards: list[dict[str, Any]] = []
    for row in rows[: max(1, int(limit))]:
        features = row.get("features") or {}
        prediction = await scorer.predict_structured(customer_features=features)
        if prediction.get("status") in {"not_trained", "insufficient_data"} and not trained:
            # Still emit a review card so UI is not empty when gate is building.
            cards.append(
                {
                    "id": f"churn-pending-{row.get('customer_id')}",
                    "kind": "churn_risk_pending",
                    "title": f"Account {row.get('customer_id')}: awaiting trained model",
                    "reason": (
                        f"Labeled signal stored ({gate['current']}/{gate['required']}). "
                        "Train churn_risk_scorer once the gate is ready."
                    ),
                    "evidence": {
                        "customerId": row.get("customer_id"),
                        "features": features,
                        "gate": gate,
                    },
                    "href": "/intelligence/predictive",
                    "advisory_only": True,
                    "executable": False,
                }
            )
            continue
        cards.append(_card(customer_id=str(row.get("customer_id")), prediction=prediction))

    # Sort highest risk first when scores exist.
    def _sort_key(card: dict[str, Any]) -> float:
        evidence = card.get("evidence") or {}
        return -float(evidence.get("riskScore") or 0.0)

    cards.sort(key=_sort_key)

    return {
        "recommendations": cards,
        "gate": gate,
        "trained": trained,
        "advisory_only": True,
        "auto_contact": False,
        "forbidden_actions": list(_FORBIDDEN_ACTIONS),
        "note": "Suggest-only churn advisory. Human review required; never auto-contacts.",
    }
