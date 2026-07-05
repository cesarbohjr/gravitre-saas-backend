"""Training readiness signals for org-scoped ML retraining."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.learning_to_rank import count_training_examples
from app.services.intelligence_evaluation_service import get_intelligence_evaluation_service
from app.services.outcome_learning_service import get_outcome_learning_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

RETRAIN_COOLDOWN_DAYS = 14


class TrainingSignalService:
    """
    Uses outcome learning and evaluations to identify retraining readiness.
    Integrates with MLModelTrainingWorkflow — never auto-trains outside scheduled rules.
    """

    MODEL_MIN_THRESHOLDS: dict[str, dict[str, int]] = {
        "intent_classifier": {"min_labeled_queries": 50},
        "workflow_anomaly_detector": {"min_workflow_runs": 30},
        "retrieval_ranker": {"min_evaluation_examples": 100},
        "revenue_forecaster": {"min_history_points": 14},
        "churn_risk_scorer": {"min_customer_signals": 30},
        "sla_breach_predictor": {"min_ticket_volume_rows": 60},
        "deal_loss_scorer": {"min_measured_deal_outcomes": 25},
        "capacity_forecaster": {"min_capacity_observations": 21},
        "workflow_duration_forecaster": {"min_workflow_runs": 30},
        "workflow_success_predictor": {"min_workflow_runs": 30},
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._outcomes = get_outcome_learning_service(self.settings)
        self._evaluations = get_intelligence_evaluation_service(self.settings)

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def _count_workflow_runs(self, org_id: str) -> int:
        try:
            resp = (
                self._client()
                .table("workflow_runs")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .execute()
            )
            return int(resp.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    async def _last_trained_at(self, org_id: str, model_name: str) -> str | None:
        try:
            from app.ml.base import ModelType
            from app.ml.registry import get_model_registry

            registry = get_model_registry()
            models = await registry.list_models(org_id=org_id, model_type=ModelType.CLASSIFIER)
            match = next((m for m in models if m.name == model_name), None)
            if match and match.updated_at:
                return match.updated_at.isoformat()
        except Exception:  # noqa: BLE001
            pass
        return None

    async def get_training_readiness(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        by_model: dict[str, Any] = {}
        for model_name, thresholds in self.MODEL_MIN_THRESHOLDS.items():
            status = "insufficient_data"
            signals_available = 0
            min_required = next(iter(thresholds.values()), 10)
            if "min_labeled_queries" in thresholds:
                try:
                    from app.services.company_intelligence_collectors import collect_query_corpus

                    corpus = await collect_query_corpus(org_id, settings=self.settings, client=client)
                    signals_available = len(corpus or [])
                except Exception:  # noqa: BLE001
                    signals_available = 0
                min_required = thresholds["min_labeled_queries"]
            elif "min_workflow_runs" in thresholds:
                signals_available = await self._count_workflow_runs(org_id)
                min_required = thresholds["min_workflow_runs"]
            elif "min_evaluation_examples" in thresholds:
                signals_available = await count_training_examples(org_id, client)
                min_required = thresholds["min_evaluation_examples"]
            elif "min_history_points" in thresholds or "min_customer_signals" in thresholds:
                candidates = await self._outcomes.get_training_signal_candidates(org_id)
                signals_available = len(candidates)
                min_required = thresholds.get("min_history_points") or thresholds.get("min_customer_signals") or 10
            elif "min_ticket_volume_rows" in thresholds or "min_capacity_observations" in thresholds:
                try:
                    from app.ml.model_catalog import _count_org_data_points

                    counts = _count_org_data_points(org_id, model_name, self.settings).get("data_counts") or {}
                    if "min_ticket_volume_rows" in thresholds:
                        signals_available = int(counts.get("ticket_volume_rows") or 0)
                        min_required = thresholds["min_ticket_volume_rows"]
                    else:
                        signals_available = int(counts.get("capacity_observations") or 0)
                        min_required = thresholds["min_capacity_observations"]
                except Exception:  # noqa: BLE001
                    signals_available = 0
            elif "min_measured_deal_outcomes" in thresholds:
                try:
                    from app.ml.model_catalog import _count_org_data_points

                    counts = _count_org_data_points(org_id, model_name, self.settings).get("data_counts") or {}
                    signals_available = int(counts.get("measured_deal_outcomes") or 0)
                    min_required = thresholds["min_measured_deal_outcomes"]
                except Exception:  # noqa: BLE001
                    signals_available = 0
            last_trained = await self._last_trained_at(org_id, model_name)
            if signals_available >= min_required:
                if last_trained:
                    trained_at = datetime.fromisoformat(last_trained.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - trained_at < timedelta(days=RETRAIN_COOLDOWN_DAYS):
                        status = "already_trained_recently"
                    else:
                        status = "ready"
                else:
                    status = "ready"
            by_model[model_name] = {
                "status": status,
                "signals_available": signals_available,
                "min_required": min_required,
                "last_trained_at": last_trained,
            }
        ready_orgs = sum(1 for m in by_model.values() if m.get("status") == "ready")
        recommendations = [
            {"model_name": name, "reason": "threshold_met_and_cooldown_elapsed"}
            for name, info in by_model.items()
            if info.get("status") == "ready"
        ]
        return {
            "by_model": by_model,
            "orgs_ready_for_training": ready_orgs,
            "recommended_next_training": recommendations,
        }

    async def get_domain_optimization_signals(self, org_id: str) -> dict[str, Any]:
        readiness = await self.get_training_readiness(org_id)
        return {
            "retrain_candidates": readiness.get("recommended_next_training") or [],
            "by_model": readiness.get("by_model") or {},
            "advisory_only": True,
            "auto_training_enabled": False,
        }

    async def recommend_retraining(self, org_id: str) -> list[dict[str, Any]]:
        readiness = await self.get_training_readiness(org_id)
        recommended: list[dict[str, Any]] = []
        for model_name, info in readiness.get("by_model", {}).items():
            if info.get("status") != "ready":
                continue
            recommended.append({"model_name": model_name, "reason": "threshold_met_and_cooldown_elapsed"})
        return recommended

    async def export_training_signals(self, org_id: str, model_name: str) -> dict[str, Any]:
        threshold = self.MODEL_MIN_THRESHOLDS.get(model_name, {})
        min_val = min(threshold.values()) if threshold else 10
        predictive_ops_models = {
            "sla_breach_predictor",
            "deal_loss_scorer",
            "capacity_forecaster",
        }
        if model_name in predictive_ops_models or "min_ticket_volume_rows" in threshold:
            readiness = await self.get_training_readiness(org_id)
            info = readiness.get("by_model", {}).get(model_name, {})
            signals_available = int(info.get("signals_available") or 0)
            if signals_available < min_val:
                return {
                    "status": "insufficient_data",
                    "model": model_name,
                    "signals_available": signals_available,
                    "min_required": threshold,
                }
            return {
                "status": "ready",
                "model": model_name,
                "signals_available": signals_available,
                "signals": [{"model_name": model_name, "count": signals_available}],
            }
        candidates = await self._outcomes.get_training_signal_candidates(org_id)
        model_signals = [c for c in candidates if c.get("model_name") == model_name]
        if len(model_signals) < min_val:
            return {
                "status": "insufficient_data",
                "model": model_name,
                "signals_available": len(model_signals),
                "min_required": threshold,
            }
        return {"status": "ready", "model": model_name, "signals": model_signals}

    async def queue_training_if_threshold_met(self, org_id: str, model_name: str) -> dict[str, Any]:
        export = await self.export_training_signals(org_id, model_name)
        if export["status"] != "ready":
            return export
        if os.environ.get("TEMPORAL_HOST"):
            try:
                from app.temporal.starters import start_ml_model_training_workflow

                started = await start_ml_model_training_workflow(org_id, model_name)
                if started.get("temporal"):
                    return {"status": "queued", **started}
            except Exception as exc:  # noqa: BLE001
                logger.debug("queue_training_temporal_skipped error=%s", exc)
        return {
            "status": "ready_for_manual_trigger",
            "signals": export["signals"],
            "trigger_endpoint": f"/api/admin/ml/models/{model_name}/train",
        }


_training_signal_service: TrainingSignalService | None = None


def get_training_signal_service(settings: Settings | None = None) -> TrainingSignalService:
    global _training_signal_service
    if _training_signal_service is None or settings is not None:
        _training_signal_service = TrainingSignalService(settings)
    return _training_signal_service
