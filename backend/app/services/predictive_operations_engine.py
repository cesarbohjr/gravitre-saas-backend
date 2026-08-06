"""Unified predictive operations organized by domain packs."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.ml.base import ModelStatus
from app.ml.model_catalog import GRAVITRE_ML_CATALOG, get_model_instance, get_org_model_status
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
            "deal_loss_scorer",
        ],
        "support": [
            "churn_risk_scorer",
            "workflow_anomaly_detector",
            "sla_breach_predictor",
            "capacity_forecaster",
        ],
        "operations": [
            "workflow_duration_forecaster",
            "workflow_anomaly_detector",
            "workflow_success_predictor",
            "capacity_forecaster",
        ],
        "finance": ["revenue_forecaster"],
        "marketing": [
            "churn_risk_scorer",
            "revenue_forecaster",
        ],
        "customer_success": [
            "churn_risk_scorer",
            "sla_breach_predictor",
        ],
    }

    RISK_THRESHOLD = 0.65

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def _predict_model(self, org_id: str, model_name: str) -> dict[str, Any]:
        if model_name not in GRAVITRE_ML_CATALOG:
            return {"status": "planned", "model": model_name, "advisory_only": True}
        meta = GRAVITRE_ML_CATALOG[model_name]
        status = meta["status"]
        if status == ModelStatus.DISABLED:
            raise ModelPlannedError(model_name)
        if status == ModelStatus.PLANNED:
            instance = get_model_instance(model_name)
            structured = await instance.predict_structured(org_id=org_id, settings=self.settings)
            return {
                "status": "planned",
                "model": model_name,
                "reason": structured.get("reason"),
                "data_gate": structured.get("data_gate"),
                "fallback": structured.get("fallback"),
                "advisory_only": True,
                "scope_note": SCOPE_NOTE,
            }

        payload = await get_org_model_status(org_id, model_name, settings=self.settings)
        if payload.get("catalog_status") != ModelStatus.TRAINED.value:
            raise ModelNotTrainedError(model_name)

        from app.ml.model_catalog import load_org_trained_catalog_model

        instance = await load_org_trained_catalog_model(org_id, model_name, settings=self.settings)
        try:
            structured = await instance.predict_structured(org_id=org_id, settings=self.settings)
        except TypeError:
            structured = await instance.predict_structured()

        result_status = str(structured.get("status") or "ok")
        if result_status in {"not_available", "not_trained", "insufficient_data"}:
            raise ModelNotTrainedError(model_name)

        risk_score = structured.get("risk_score")
        if risk_score is None:
            risk_score = structured.get("confidence")
        return {
            "status": "ok",
            "model": model_name,
            "catalog_status": payload.get("catalog_status"),
            "activation": payload.get("activation"),
            "prediction": structured,
            "risk_score": float(risk_score) if risk_score is not None else None,
            "advisory_only": True,
            "scope_note": SCOPE_NOTE,
        }

    async def run_domain_predictions(
        self,
        org_id: str,
        domain: str,
    ) -> dict[str, Any]:
        pack = self.DOMAIN_PREDICTION_PACKS.get(domain, [])

        async def _one(model_name: str) -> tuple[str, dict[str, Any]]:
            try:
                return model_name, await self._predict_model(org_id, model_name)
            except ModelNotTrainedError:
                return model_name, {
                    "status": "insufficient_data",
                    "model": model_name,
                    "advisory_only": True,
                }
            except ModelPlannedError:
                return model_name, {
                    "status": "planned",
                    "model": model_name,
                    "advisory_only": True,
                }

        pairs = await asyncio.gather(*[_one(name) for name in pack]) if pack else []
        results = {name: payload for name, payload in pairs}
        return {
            "domain": domain,
            "predictions": results,
            "advisory_only": True,
            "scope_note": SCOPE_NOTE,
        }

    async def generate_early_warning_alerts(
        self,
        org_id: str,
        *,
        domains: list[str] | None = None,
        persist_suggestions: bool = True,
        precomputed: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict]:
        """Build early-warning alerts.

        Mount/chat paths should pass ``domains=[current]`` and
        ``persist_suggestions=False`` — the historical default looped every
        domain pack sequentially and re-ran suggestion detection on every
        `/business-signals` hit (multi-second mount tax).
        """
        alerts: list[dict] = []
        selected = domains or list(self.DOMAIN_PREDICTION_PACKS.keys())

        async def _domain(domain: str) -> list[dict]:
            if precomputed and domain in precomputed:
                predictions = precomputed[domain]
            else:
                predictions = await self.run_domain_predictions(org_id, domain)
            out: list[dict] = []
            for model_name, payload in (predictions.get("predictions") or {}).items():
                if payload.get("status") != "ok":
                    continue
                risk = payload.get("risk_score")
                if risk is None:
                    continue
                if float(risk) >= self.RISK_THRESHOLD:
                    out.append(
                        {
                            "domain": domain,
                            "model": model_name,
                            "riskScore": float(risk),
                            "route": "optimization_suggestions",
                            "advisory_only": True,
                            "scope_note": SCOPE_NOTE,
                        }
                    )
            return out

        nested = await asyncio.gather(*[_domain(d) for d in selected]) if selected else []
        for batch in nested:
            alerts.extend(batch)

        if alerts and persist_suggestions:
            opt = get_optimization_suggestion_service(self.settings)
            await opt.detect_suggestions_for_org(org_id)
            await opt.list_suggestions(org_id, status="pending_review", limit=5)
        return alerts


_engine: PredictiveOperationsEngine | None = None


def get_predictive_operations_engine(settings: Settings | None = None) -> PredictiveOperationsEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = PredictiveOperationsEngine(settings)
    return _engine
