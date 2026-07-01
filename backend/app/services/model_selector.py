"""Model selection across ML catalog and model_router LLM tiers."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.ml.base import ModelStatus
from app.ml.model_catalog import GRAVITRE_ML_CATALOG, get_org_model_status
from app.ml.registry import get_model_registry
from app.services.model_router import ModelRouter

ML_TASK_MAP: dict[str, str] = {
    "data_analysis": "workflow_anomaly_detector",
    "analytics": "workflow_anomaly_detector",
    "workflow_execution": "workflow_success_predictor",
    "question_answering": "intent_classifier",
}

BASE_MODEL_ALIASES: dict[str, tuple[str, ...]] = {
    "workflow_anomaly_detector": ("anomaly_detector", "workflow_anomaly_detector"),
    "workflow_success_predictor": ("success_predictor", "workflow_success_predictor"),
    "intent_classifier": ("intent_classifier",),
}


class ModelSelector:
    """
    Selects internal ML models when trained for the org, otherwise LLM tiers via model_router.
    Never presents PLANNED model output as real ML.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._router = ModelRouter(self.settings)

    async def select(self, org_id: str, classification: dict[str, Any]) -> dict[str, Any]:
        task_type = str(classification.get("intent") or "question_answering")
        ml_candidate = ML_TASK_MAP.get(task_type)
        if ml_candidate and ml_candidate in GRAVITRE_ML_CATALOG:
            catalog_meta = GRAVITRE_ML_CATALOG[ml_candidate]
            if catalog_meta["status"] == ModelStatus.PLANNED:
                return self._llm_selection(task_type, classification, reason=f"{ml_candidate} is PLANNED")
            if catalog_meta["status"] == ModelStatus.DISABLED:
                return self._llm_selection(task_type, classification, reason=f"{ml_candidate} is DISABLED")
            try:
                if await self._org_has_deployed_model(org_id, ml_candidate):
                    org_status = await get_org_model_status(org_id, ml_candidate, settings=self.settings)
                    return {
                        "primary_model": "ml_internal",
                        "ml_model_name": ml_candidate,
                        "llm_tier": "fast",
                        "fallback": "llm_standard",
                        "reason": f"Trained {ml_candidate} available for org",
                        "catalog_status": org_status.get("catalog_status"),
                    }
            except Exception:  # noqa: BLE001
                pass
        return self._llm_selection(task_type, classification)

    async def _org_has_deployed_model(self, org_id: str, catalog_name: str) -> bool:
        aliases = BASE_MODEL_ALIASES.get(catalog_name, (catalog_name,))
        try:
            registry = get_model_registry()
            models = await registry.list_models(org_id, status=ModelStatus.DEPLOYED)
            for model in models:
                base = str(getattr(model, "base_model", "") or "")
                if base in aliases or model.name in aliases:
                    return True
            models_ready = await registry.list_models(org_id, status=ModelStatus.READY)
            for model in models_ready:
                base = str(getattr(model, "base_model", "") or "")
                if base in aliases or model.name in aliases:
                    return True
        except Exception:  # noqa: BLE001
            return False
        return False

    def _llm_selection(
        self,
        task_type: str,
        classification: dict[str, Any],
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        sensitivity = str(classification.get("risk_level") or "low")
        llm_model = self._router.route_for_sensitivity(
            sensitivity,
            "high" if task_type in {"workflow_execution", "data_analysis"} else "medium",
        )
        tier = "fast" if classification.get("latency_target") == "tier_1" else "standard"
        if task_type in {"workflow_execution", "data_analysis"}:
            tier = "reasoning"
        return {
            "primary_model": "llm",
            "ml_model_name": None,
            "llm_tier": tier,
            "llm_model": llm_model,
            "fallback": "llm_fast",
            "reason": reason or f"No trained ML model for {task_type} — using LLM {tier} tier",
        }


_model_selector: ModelSelector | None = None


def get_model_selector(settings: Settings | None = None) -> ModelSelector:
    global _model_selector
    if _model_selector is None or settings is not None:
        _model_selector = ModelSelector(settings)
    return _model_selector
