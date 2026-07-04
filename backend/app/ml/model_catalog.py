"""Gravitre ML model catalog — all 14+ model types with honest status."""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.active_learning import ActiveLearningCoordinator
from app.ml.anomaly import AnomalyDetector
from app.ml.base import ModelStatus
from app.ml.causal_analysis import CausalImpactAnalyzer
from app.ml.churn_scoring import ChurnRiskScorer
from app.ml.classifiers import IntentClassifier
from app.ml.clustering import QueryClusterer
from app.ml.domain_llm import DomainSpecificLLMRouter
from app.ml.federated_learning import FederatedLearningCoordinator
from app.ml.forecasting import WorkflowForecaster, WorkflowSuccessPredictor
from app.ml.generative_models import DiffusionModelConnector
from app.ml.graph_models import GraphNeuralNetworkScorer
from app.ml.learning_to_rank import RetrievalRanker
from app.ml.memory_promotion_scorer import MemoryPromotionScorer
from app.ml.meta_learning import MetaLearningAdaptor
from app.ml.multimodal_models import MultimodalRouter
from app.ml.neuro_symbolic import NeuroSymbolicReasoningEngine
from app.ml.planning_models import AgentPlanningModel
from app.ml.predictive_ops_models import CapacityForecaster, DealLossScorer, SlaBreachPredictor
from app.ml.retrieval_learning import RetrievalMemoryLearner
from app.ml.revenue_forecasting import RevenueForecaster
from app.ml.self_supervised import SelfSupervisedEmbeddingLearner
from app.ml.world_models import WorldModelScaffold
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

GRAVITRE_ML_CATALOG: dict[str, dict[str, Any]] = {
    "intent_classifier": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["query_routing", "department_detection"],
        "min_data": "50 labeled queries",
        "fallback": "rule_based_classify_query",
        "advisory_only": False,
    },
    "workflow_anomaly_detector": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["bottleneck_detection"],
        "min_data": "30 workflow runs",
        "fallback": "threshold_based_detection",
        "advisory_only": True,
    },
    "workflow_duration_forecaster": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["performance_planning"],
        "min_data": "30 workflow runs",
        "fallback": "historical_average",
        "advisory_only": True,
    },
    "workflow_success_predictor": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["risk_identification"],
        "min_data": "30 workflow runs",
        "fallback": "historical_success_rate",
        "advisory_only": True,
    },
    "retrieval_ranker": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["rag_quality_improvement"],
        "min_data": "100 evaluated responses",
        "fallback": "fixed_reliability_weight",
        "advisory_only": False,
    },
    "query_clusterer": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["knowledge_gap_detection"],
        "min_data": "40 distinct queries",
        "fallback": "no_clustering",
        "advisory_only": False,
    },
    "memory_promotion_scorer": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["memory_promotion_prioritization"],
        "min_data": "15 resolved promotion candidates",
        "fallback": "rule_based_promotion_thresholds",
        "advisory_only": True,
    },
    "retrieval_memory_learner": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["unified_retrieval_quality"],
        "note": "Unified interface over v3/v4/v5/v7",
        "advisory_only": False,
    },
    "revenue_forecaster": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["revenue_forecasting"],
        "activation": "14+ revenue data points from CRM/finance connectors",
        "fallback": "insufficient_data_response",
        "advisory_only": True,
    },
    "churn_risk_scorer": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["customer_risk_scoring"],
        "activation": "30+ customer engagement data points",
        "fallback": "rule_based_risk_signals",
        "advisory_only": True,
    },
    "sla_breach_predictor": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["support_sla_breach_risk"],
        "activation": "60+ support tickets with SLA resolution timestamps",
        "fallback": "support_backlog correlational detector",
        "advisory_only": True,
    },
    "deal_loss_scorer": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["deal_loss_probability"],
        "activation": "25+ measured CRM deal win/loss outcomes",
        "fallback": "stalled_deal correlational detector",
        "advisory_only": True,
    },
    "capacity_forecaster": {
        "status": ModelStatus.TRAINED,
        "use_cases": ["support_capacity_forecasting"],
        "activation": "21+ daily ticket volume observations",
        "fallback": "business_digital_twin support_capacity domain",
        "advisory_only": True,
    },
    "causal_impact_analyzer": {
        "status": ModelStatus.PLANNED,
        "use_cases": ["causal_business_impact"],
        "activation": "30+ pre/post action observations per metric",
        "fallback": "correlation_with_disclosure",
        "advisory_only": True,
    },
    "graph_neural_network": {
        "status": ModelStatus.PLANNED,
        "use_cases": ["relationship_scoring"],
        "activation": "10k+ entity relationships, PyTorch Geometric, GPU",
        "fallback": "postgres_confidence_traversal",
        "advisory_only": False,
    },
    "multimodal_router": {
        "status": ModelStatus.PLANNED,
        "use_cases": ["image_document_processing"],
        "activation": "model_router vision tier (partially active)",
        "advisory_only": False,
    },
    "active_learning": {
        "status": ModelStatus.PLANNED,
        "use_cases": ["label_prioritization"],
        "activation": "uncertainty sampling over InferenceService distributions",
        "advisory_only": False,
    },
    "meta_learning": {
        "status": ModelStatus.PLANNED,
        "activation": "Same as FederatedLearning",
        "advisory_only": False,
    },
    "neuro_symbolic": {
        "status": ModelStatus.PLANNED,
        "note": "LLM + structured rules injection is current equivalent",
        "advisory_only": False,
    },
    "agentic_planning": {
        "status": ModelStatus.PLANNED,
        "activation": "Accumulate v8 trajectory data, extend ReActEngine",
        "advisory_only": True,
    },
    "world_model": {
        "status": ModelStatus.PLANNED,
        "activation": "6+ months v8 outcome data + CausalImpactAnalyzer active",
        "advisory_only": True,
    },
    "domain_specific_llm": {
        "status": ModelStatus.PLANNED,
        "activation": "1000+ examples per dept, FineTunedLLM pipeline",
        "advisory_only": False,
    },
    "federated_learning": {
        "status": ModelStatus.DISABLED,
        "activation": "Legal review, consent mechanism, Flower framework, 100+ participating orgs",
        "advisory_only": False,
    },
    "diffusion_model": {
        "status": ModelStatus.PLANNED,
        "activation": "Image generation provider via ToolRegistry connector",
        "advisory_only": False,
    },
    "self_supervised_embeddings": {
        "status": ModelStatus.PLANNED,
        "note": "Current embedding model sufficient. Activate if v7 shows quality gap.",
        "advisory_only": False,
    },
}

_MODEL_CLASS_MAP: dict[str, Callable[[], Any]] = {
    "intent_classifier": IntentClassifier,
    "workflow_anomaly_detector": AnomalyDetector,
    "workflow_duration_forecaster": WorkflowForecaster,
    "workflow_success_predictor": WorkflowSuccessPredictor,
    "retrieval_ranker": RetrievalRanker,
    "query_clusterer": QueryClusterer,
    "memory_promotion_scorer": MemoryPromotionScorer,
    "retrieval_memory_learner": RetrievalMemoryLearner,
    "revenue_forecaster": RevenueForecaster,
    "churn_risk_scorer": ChurnRiskScorer,
    "sla_breach_predictor": SlaBreachPredictor,
    "deal_loss_scorer": DealLossScorer,
    "capacity_forecaster": CapacityForecaster,
    "causal_impact_analyzer": CausalImpactAnalyzer,
    "graph_neural_network": GraphNeuralNetworkScorer,
    "multimodal_router": MultimodalRouter,
    "active_learning": ActiveLearningCoordinator,
    "meta_learning": MetaLearningAdaptor,
    "neuro_symbolic": NeuroSymbolicReasoningEngine,
    "agentic_planning": AgentPlanningModel,
    "world_model": WorldModelScaffold,
    "domain_specific_llm": DomainSpecificLLMRouter,
    "federated_learning": FederatedLearningCoordinator,
    "diffusion_model": DiffusionModelConnector,
    "self_supervised_embeddings": SelfSupervisedEmbeddingLearner,
}


def get_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for name, meta in GRAVITRE_ML_CATALOG.items():
        entry = dict(meta)
        status = entry.get("status")
        if isinstance(status, ModelStatus):
            entry["status"] = status.value
        catalog[name] = entry
    return catalog


def get_model_instance(model_name: str) -> Any:
    factory = _MODEL_CLASS_MAP.get(model_name)
    if not factory:
        raise ValueError(f"Unknown catalog model: {model_name}")
    return factory()


def _count_org_data_points(org_id: str, model_name: str, settings: Settings) -> dict[str, Any]:
    meta = GRAVITRE_ML_CATALOG[model_name]
    activation = meta.get("activation") or meta.get("min_data") or ""
    counts: dict[str, int] = {}

    try:
        client = get_supabase_client(settings)
    except Exception as exc:  # noqa: BLE001
        logger.debug("_count_org_data_points client init failed model=%s error=%s", model_name, exc)
        return {"activation_requirement": activation, "data_counts": counts}

    try:
        if model_name in {"workflow_anomaly_detector", "workflow_duration_forecaster", "workflow_success_predictor"}:
            rows = client.table("workflow_runs").select("id", count="exact").eq("org_id", org_id).execute()
            counts["workflow_runs"] = int(rows.count or 0)
        elif model_name == "intent_classifier":
            rows = client.table("user_query_patterns").select("id", count="exact").eq("org_id", org_id).execute()
            counts["logged_queries"] = int(rows.count or 0)
        elif model_name == "query_clusterer":
            rows = client.table("user_query_patterns").select("id", count="exact").eq("org_id", org_id).execute()
            counts["logged_queries"] = int(rows.count or 0)
        elif model_name == "retrieval_ranker":
            rows = (
                client.table("rag_chunk_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .not_.is_("outcome_helpful", "null")
                .execute()
            )
            counts["scored_chunks"] = int(rows.count or 0)
        elif model_name == "memory_promotion_scorer":
            rows = (
                client.table("memory_promotion_candidates")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .in_("status", ["approved", "auto_promoted", "written", "rejected", "rolled_back", "expired"])
                .execute()
            )
            counts["resolved_candidates"] = int(rows.count or 0)
        elif model_name == "revenue_forecaster":
            rows = (
                client.table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .execute()
            )
            counts["outcome_rows"] = int(rows.count or 0)
        elif model_name == "churn_risk_scorer":
            rows = client.table("agent_action_outcomes").select("id", count="exact").eq("org_id", org_id).execute()
            counts["outcome_rows"] = int(rows.count or 0)
        elif model_name == "sla_breach_predictor":
            rows = (
                client.table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("metric_name", "ticket_volume")
                .execute()
            )
            counts["ticket_volume_rows"] = int(rows.count or 0)
        elif model_name == "deal_loss_scorer":
            rows = (
                client.table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("target_entity_type", "deal")
                .not_.is_("measured_at", "null")
                .execute()
            )
            counts["measured_deal_outcomes"] = int(rows.count or 0)
        elif model_name == "capacity_forecaster":
            rows = (
                client.table("agent_action_outcomes")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("metric_name", "ticket_volume")
                .execute()
            )
            counts["capacity_observations"] = int(rows.count or 0)
        elif model_name == "graph_neural_network":
            rows = (
                client.table("org_entity_relationships")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .execute()
            )
            counts["relationship_rows"] = int(rows.count or 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "_count_org_data_points query failed model=%s org_id=%s error=%s",
            model_name,
            org_id,
            exc,
        )

    return {"activation_requirement": activation, "data_counts": counts}


async def get_org_model_status(org_id: str, model_name: str, *, settings: Settings | None = None) -> dict[str, Any]:
    active = settings or get_settings()
    if model_name not in GRAVITRE_ML_CATALOG:
        raise ValueError(f"Unknown catalog model: {model_name}")
    meta = GRAVITRE_ML_CATALOG[model_name]
    status = meta["status"]
    payload = {
        "model_name": model_name,
        "catalog_status": status.value,
        "advisory_only": bool(meta.get("advisory_only", False)),
        "use_cases": meta.get("use_cases", []),
        "activation": meta.get("activation") or meta.get("min_data") or meta.get("note"),
        "fallback": meta.get("fallback"),
    }
    if status == ModelStatus.TRAINED:
        payload.update(_count_org_data_points(org_id, model_name, active))
    elif status == ModelStatus.PLANNED and model_name in {
        "sla_breach_predictor",
        "deal_loss_scorer",
        "capacity_forecaster",
    }:
        payload.update(_count_org_data_points(org_id, model_name, active))
    return payload


async def build_ml_catalog_dashboard(org_id: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """Return catalog + per-org training status for Intelligence Center and admin surfaces."""
    active = settings or get_settings()
    catalog = get_catalog()
    org_status: dict[str, Any] = {}
    for name, meta in catalog.items():
        if meta.get("status") != "trained":
            continue
        try:
            org_status[name] = await get_org_model_status(org_id, name, settings=active)
        except Exception as exc:  # noqa: BLE001
            logger.debug("org_model_status_skipped name=%s org_id=%s error=%s", name, org_id, exc)
    try:
        from app.services.strategy_performance_ledger import get_strategy_performance_ledger

        outcome_scores = await get_strategy_performance_ledger(active).load_model_outcome_scores(org_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("load_model_outcome_scores failed org_id=%s error=%s", org_id, exc)
        outcome_scores = {}
    return {"catalog": catalog, "orgTrainingStatus": org_status, "outcomeScores": outcome_scores}


async def load_org_trained_catalog_model(
    org_id: str,
    model_name: str,
    *,
    settings: Settings | None = None,
) -> Any:
    """Return catalog instance with org artifact loaded when deployed."""
    from app.ml.intelligence_training import CATALOG_MODEL_NAMES
    from app.ml.registry import get_model_registry

    active = settings or get_settings()
    instance = get_model_instance(model_name)
    registry_name = CATALOG_MODEL_NAMES.get(model_name, model_name)
    try:
        registry = get_model_registry()
        models = await registry.list_models(org_id=org_id)
        match = next((m for m in models if m.name == registry_name and m.deployed_version), None)
        if match:
            artifact = await registry.load_model_artifact(match.id, match.deployed_version)
            instance.load(artifact)
    except Exception:  # noqa: BLE001
        pass
    return instance


async def train_ml_model_for_org(org_id: str, model_name: str, *, settings: Settings | None = None) -> dict[str, Any]:
    active = settings or get_settings()
    if model_name not in GRAVITRE_ML_CATALOG:
        raise ValueError(f"Unknown catalog model: {model_name}")
    meta = GRAVITRE_ML_CATALOG[model_name]
    if meta["status"] != ModelStatus.TRAINED:
        raise ValueError(f"{model_name} is {meta['status'].value}; training not available")

    start = time.perf_counter()

    if model_name in {"causal_impact_analyzer", "graph_neural_network", "multimodal_router"}:
        instance = get_model_instance(model_name)
        structured = await instance.predict_structured()
        return {"trained": False, "result": structured}

    from app.ml.intelligence_training import TRAINING_DISPATCH, train_catalog_model

    if model_name not in TRAINING_DISPATCH:
        raise ValueError(f"No training pipeline for {model_name}")

    result = await train_catalog_model(org_id, model_name, settings=active)
    used_fallback = not result.get("trained", False)
    latency_ms = int((time.perf_counter() - start) * 1000)
    await _log_ml_prediction(active, org_id, model_name, meta["status"].value, latency_ms, used_fallback)
    return {**result, "latency_ms": latency_ms}


async def _log_ml_prediction(
    settings: Settings,
    org_id: str,
    model_name: str,
    model_status: str,
    latency_ms: int,
    used_fallback: bool,
) -> None:
    try:
        from app.services.clickhouse_service import get_clickhouse_service

        ch = get_clickhouse_service()
        if not ch.is_available():
            return
        await ch.insert_events(
            "gravitre.ml_predictions",
            [
                {
                    "org_id": org_id,
                    "model_name": model_name,
                    "model_status": model_status,
                    "confidence": 0.0,
                    "latency_ms": latency_ms,
                    "used_fallback": used_fallback,
                    "created_at": datetime.now(timezone.utc),
                }
            ],
        )
    except Exception:  # noqa: BLE001
        return
