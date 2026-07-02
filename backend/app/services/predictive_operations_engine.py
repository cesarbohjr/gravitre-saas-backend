"""Unified predictive operations organized by domain packs."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.ml.base import ModelStatus
from app.ml.model_catalog import GRAVITRE_ML_CATALOG, get_org_model_status
from app.services.optimization_suggestion_service import get_optimization_suggestion_service

SCOPE_NOTE = (
    "PredictiveOperationsEngine routes to GRAVITRE_ML_CATALOG via catalog status checks. "
    "Never builds parallel model infrastructure. All outputs are advisory_only."
)


class ModelNotTrainedError(Exception):
    """Raised when org has not trained a catalog model."""


class ModelPlannedError(Exception):
    """Raised when catalog model is planned/disabled."""


class PredictiveOperationsEngine:
    """
    Unified access to predictive capabilities organized by domain.
    Routes to GRAVITRE_ML_CATALOG — never builds parallel model infrastructure.
    """

    DOMAIN_PREDICTION_PACKS = {
        "sales": [
            "churn_risk_scorer",
            "revenue_forecaster",
            "workflow_success_predictor",
        ],
        "support": [
            "churn_risk_scorer",
            "workflow_anomaly_detector",
        ],
        "operations": [
            "workflow_duration_forecaster",
            "workflow_anomaly_detector",
            "workflow_success_predictor",
        ],
        "finance": ["revenue_forecaster"],
        "marketing": [
            "churn_risk_scorer",
            "revenue_forecaster",
        ],
    }

    RISK_THRESHOLD = 0.65

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def _predict_model(self, org_id: str, model_name: str) -> dict[str, Any]:
        if model_name not in GRAVITRE_ML_CATALOG:
            return {"status": "planned", "model": model_name}
        meta = GRAVITRE_ML_CATALOG[model_name]
        status = meta["status"]
        if status == ModelStatus.PLANNED:
            raise ModelPlannedError(model_name)
        if status == ModelStatus.DISABLED:
            raise ModelPlannedError(model_name)
        payload = await get_org_model_status(org_id, model_name, settings=self.settings)
        if payload.get("catalog_status") != ModelStatus.TRAINED.value:
            raise ModelNotTrainedError(model_name)
        return {
            "status": "ok",
            "model": model_name,
            "catalog_status": payload.get("catalog_status"),
            "activation": payload.get("activation"),
            "advisory_only": True,
            "scope_note": SCOPE_NOTE,
        }

    async def run_domain_predictions(
        self,
        org_id: str,
        domain: str,
    ) -> dict[str, Any]:
        pack = self.DOMAIN_PREDICTION_PACKS.get(domain, [])
        results: dict[str, Any] = {}
        for model_name in pack:
            try:
                results[model_name] = await self._predict_model(org_id, model_name)
            except ModelNotTrainedError:
                results[model_name] = {
                    "status": "insufficient_data",
                    "model": model_name,
                    "advisory_only": True,
                }
            except ModelPlannedError:
                results[model_name] = {
                    "status": "planned",
                    "model": model_name,
                    "advisory_only": True,
                }
        return {
            "domain": domain,
            "predictions": results,
            "advisory_only": True,
            "scope_note": SCOPE_NOTE,
        }

    async def generate_early_warning_alerts(
        self,
        org_id: str,
    ) -> list[dict]:
        alerts: list[dict] = []
        for domain in self.DOMAIN_PREDICTION_PACKS:
            predictions = await self.run_domain_predictions(org_id, domain)
            for model_name, payload in (predictions.get("predictions") or {}).items():
                if payload.get("status") != "ok":
                    continue
                risk = float(payload.get("risk_score") or 0.55)
                if risk >= self.RISK_THRESHOLD:
                    alerts.append(
                        {
                            "domain": domain,
                            "model": model_name,
                            "riskScore": risk,
                            "route": "optimization_suggestions",
                            "advisory_only": True,
                            "scope_note": SCOPE_NOTE,
                        }
                    )
        if alerts:
            await get_optimization_suggestion_service(self.settings).list_suggestions(
                org_id,
                status="pending_review",
                limit=5,
            )
        return alerts


_engine: PredictiveOperationsEngine | None = None


def get_predictive_operations_engine(settings: Settings | None = None) -> PredictiveOperationsEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = PredictiveOperationsEngine(settings)
    return _engine
