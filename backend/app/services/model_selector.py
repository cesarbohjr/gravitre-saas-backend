"""Model selection across ML catalog and model_router LLM tiers."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.ml.base import ModelStatus
from app.ml.model_catalog import GRAVITRE_ML_CATALOG, get_org_model_status
from app.ml.registry import get_model_registry
from app.services.learning_strategy_keys import (
    build_model_strategy_key,
    parse_base_segment_key,
    parse_segment_key,
)
from app.services.model_router import ModelRouter
from app.services.strategy_performance_ledger import get_strategy_performance_ledger

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
        segment_key = parse_segment_key(classification)
        fallback_segment_key = parse_base_segment_key(classification)
        ml_candidate = ML_TASK_MAP.get(task_type)
        if ml_candidate and ml_candidate in GRAVITRE_ML_CATALOG:
            catalog_meta = GRAVITRE_ML_CATALOG[ml_candidate]
            if catalog_meta["status"] == ModelStatus.PLANNED:
                return await self._llm_selection_with_ledger(
                    org_id,
                    task_type,
                    classification,
                    segment_key,
                    fallback_segment_key=fallback_segment_key,
                    reason=f"{ml_candidate} is PLANNED",
                )
            if catalog_meta["status"] == ModelStatus.DISABLED:
                return await self._llm_selection_with_ledger(
                    org_id,
                    task_type,
                    classification,
                    segment_key,
                    fallback_segment_key=fallback_segment_key,
                    reason=f"{ml_candidate} is DISABLED",
                )
            try:
                deployed = await self._list_deployed_ml_models(org_id)
                if deployed:
                    preferred = await self._ledger_preferred_ml(
                        org_id,
                        ml_candidate,
                        deployed,
                        segment_key,
                        fallback_segment_key,
                    )
                    ml_candidate = preferred
                if await self._org_has_deployed_model(org_id, ml_candidate):
                    org_status = await get_org_model_status(org_id, ml_candidate, settings=self.settings)
                    return {
                        "primary_model": "ml_internal",
                        "ml_model_name": ml_candidate,
                        "llm_tier": "fast",
                        "fallback": "llm_standard",
                        "reason": f"Trained {ml_candidate} available for org",
                        "catalog_status": org_status.get("catalog_status"),
                        "segment_key": segment_key,
                    }
            except Exception:  # noqa: BLE001
                pass
        return await self._llm_selection_with_ledger(
            org_id,
            task_type,
            classification,
            segment_key,
            fallback_segment_key=fallback_segment_key,
        )

    async def _list_deployed_ml_models(self, org_id: str) -> list[str]:
        deployed: list[str] = []
        for name, meta in GRAVITRE_ML_CATALOG.items():
            if meta.get("status") != ModelStatus.TRAINED:
                continue
            if await self._org_has_deployed_model(org_id, name):
                deployed.append(name)
        return deployed

    async def _ledger_preferred_ml(
        self,
        org_id: str,
        default_model: str,
        deployed: list[str],
        segment_key: str,
        fallback_segment_key: str,
    ) -> str:
        keys = [build_model_strategy_key(name) for name in deployed]
        default_key = build_model_strategy_key(default_model)
        pref = await get_strategy_performance_ledger(self.settings).choose_preferred_strategy(
            org_id,
            default_key,
            keys,
            segment_key=segment_key,
            fallback_segment_key=fallback_segment_key,
        )
        selected = str(pref.get("selected_key") or default_key)
        if selected.startswith("model:"):
            model_name = selected.split(":", 1)[1]
            if model_name in deployed:
                return model_name
        return default_model

    async def _llm_selection_with_ledger(
        self,
        org_id: str,
        task_type: str,
        classification: dict[str, Any],
        segment_key: str,
        *,
        fallback_segment_key: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        base = self._llm_selection(task_type, classification, reason=reason)
        tiers = ("fast", "standard", "reasoning")
        default_key = f"llm:{base.get('llm_tier') or 'standard'}"
        candidate_keys = [f"llm:{tier}" for tier in tiers]
        pref = await get_strategy_performance_ledger(self.settings).choose_preferred_strategy(
            org_id,
            default_key,
            candidate_keys,
            segment_key=segment_key,
            fallback_segment_key=fallback_segment_key,
        )
        selected = str(pref.get("selected_key") or default_key)
        if selected.startswith("llm:"):
            tier = selected.split(":", 1)[1]
            if tier in tiers:
                base["llm_tier"] = tier
                if pref.get("reason") == "ledger_win_rate":
                    base["reason"] = f"Ledger preferred LLM tier {tier} for {task_type}"
        base["segment_key"] = segment_key
        return base

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
