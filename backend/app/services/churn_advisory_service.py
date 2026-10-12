"""Suggest-only churn risk cards for CS / Intelligence — never auto-contacts."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.churn_feature_ingest import (
    list_churn_training_rows,
    list_unlabeled_churn_signal_rows,
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


def _log_checkable_prediction(
    client: Any, settings: Any, org_id: str, scorer: Any, customer_id: str, prediction: dict[str, Any]
) -> None:
    """Phase 6: log the score so it can be checked against the customer's real outcome."""
    from app.ml.churn_feature_ingest import CHURN_ENTITY_TYPE
    from app.ml.prediction_outcomes import (
        CHURN_HORIZON_DAYS,
        churn_prediction_payload,
        log_subject_prediction,
        outcomes_enabled,
    )

    ref = getattr(scorer, "registry_ref", None)
    if not outcomes_enabled(settings) or not isinstance(ref, dict) or not customer_id:
        return
    label, score, payload = churn_prediction_payload(prediction)
    try:
        log_subject_prediction(
            client,
            settings,
            org_id=org_id,
            model_id=ref["model_id"],
            version=ref["version"],
            subject_type=CHURN_ENTITY_TYPE,
            subject_id=customer_id,
            horizon_days=CHURN_HORIZON_DAYS,
            predicted_label=label,
            predicted_score=score,
            prediction=payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("churn_prediction_log_failed org_id=%s error=%s", org_id, type(exc).__name__)


async def build_churn_advisory_cards(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    limit: int = 25,
    log_predictions: bool = True,
) -> dict[str, Any]:
    """Score customers whose churn outcome is still unknown; suggest-only cards.

    Labelled rows (known churned/retained) are the training set and are never
    scored — that would be in-sample prediction of an already-known outcome.
    Only unresolved customer signal rows, for customers with no label, are
    scored. With none available the advisory is empty and says why.
    """
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    gate = training_gate_status(db, org_id)
    labeled_ids = {
        str(row.get("customer_id"))
        for row in list_churn_training_rows(db, org_id)
        if row.get("customer_id") is not None
    }
    rows = [
        row
        for row in list_unlabeled_churn_signal_rows(db, org_id)
        if str(row.get("customer_id")) not in labeled_ids
    ]
    if not rows:
        return {
            "recommendations": [],
            "gate": gate,
            "trained": False,
            "reason": "no_unlabeled_customer_signals",
            "advisory_only": True,
            "auto_contact": False,
            "forbidden_actions": list(_FORBIDDEN_ACTIONS),
            "note": (
                "No customers with unresolved churn signals to score. Labelled "
                "customers are training data and are not re-scored."
            ),
        }

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

    entity_model = trained and bool(getattr(scorer, "has_optional_features", lambda: False)())
    entity_flag_on = getattr(active, "churn_entity_features_enabled", False) is True
    if entity_model and not entity_flag_on:
        # A model trained with entity features would score every account on
        # imputed values with the flag off: don't use it at all.
        logger.info("churn_advisory_entity_model_needs_flag org_id=%s", org_id)
        scorer, trained = ChurnRiskScorer(), False

    batch = rows[: max(1, int(limit))]
    entity_features: list[dict[str, Any]] = [{} for _ in batch]
    if trained and entity_model and entity_flag_on:
        # The deployed model was trained with entity features: give it the same
        # aggregates, as of now (missing stays missing).
        from datetime import UTC, datetime

        from app.ml.churn_entity_features import load_entity_features

        now = datetime.now(UTC)
        entity_features, _coverage = load_entity_features(
            db, org_id, [(str(row.get("customer_id")), now) for row in batch]
        )

    cards: list[dict[str, Any]] = []
    for row, extra in zip(batch, entity_features, strict=True):
        features = {**(row.get("features") or {}), **extra}
        prediction = await scorer.predict_structured(customer_features=features)
        if prediction.get("status") in {"not_trained", "insufficient_data"} and not trained:
            # Still emit a review card so UI is not empty when gate is building.
            cards.append(
                {
                    "id": f"churn-pending-{row.get('customer_id')}",
                    "kind": "churn_risk_pending",
                    "title": f"Account {row.get('customer_id')}: awaiting trained model",
                    "reason": (
                        f"Unresolved signal stored; labelled examples "
                        f"{gate['current']}/{gate['required']}. "
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
        if trained and log_predictions:
            _log_checkable_prediction(db, active, org_id, scorer, str(row.get("customer_id")), prediction)

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
