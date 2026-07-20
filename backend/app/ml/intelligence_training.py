"""Org-scoped training for v2–v5 intelligence models and catalog persistence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.anomaly import AnomalyDetector
from app.ml.base import ModelMetrics, ModelType
from app.ml.classifiers import IntentClassifier
from app.ml.clustering import QueryClusterer
from app.ml.feature_extraction import (
    collect_workflow_run_features,
    features_to_anomaly_input,
    features_to_forecaster_train,
    features_to_success_train,
)
from app.ml.forecasting import WorkflowForecaster, WorkflowSuccessPredictor
from app.ml.learning_to_rank import (
    RETRIEVAL_RANKER_MODEL_NAME,
    RetrievalRanker,
    collect_training_examples,
    count_training_examples,
)
from app.ml.memory_promotion_scorer import MemoryPromotionScorer
from app.ml.registry import get_model_registry
from app.rag.embedding import get_embedding
from app.services.company_intelligence_collectors import collect_query_corpus
from app.services.knowledge_intelligence_service import (
    distinct_normalized_count,
    run_glossary_extraction,
    run_query_clustering,
)
from app.services.query_normalization import normalize_query
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

INTELLIGENCE_TASK_TYPE = "company_intelligence"

CATALOG_MODEL_NAMES = {
    "intent_classifier": "catalog-query-intent",
    "query_clusterer": "catalog-query-clusterer",
    "memory_promotion_scorer": "catalog-memory-promotion",
    "retrieval_ranker": RETRIEVAL_RANKER_MODEL_NAME,
    "retrieval_memory_learner": "catalog-retrieval-memory",
    "workflow_anomaly_detector": "catalog-workflow-anomaly",
    "workflow_duration_forecaster": "catalog-workflow-duration",
    "workflow_success_predictor": "catalog-workflow-success",
    "revenue_forecaster": "catalog-revenue-forecast",
    "churn_risk_scorer": "catalog-churn-risk",
    "cf_matrix_factorizer": "catalog-cf-matrix-factorizer",
    "sla_breach_predictor": "catalog-sla-breach",
    "deal_loss_scorer": "catalog-deal-loss",
    "capacity_forecaster": "catalog-capacity-forecast",
}

MIN_QUERY_ROWS = 50
MIN_CLUSTERING_ROWS = 40
MIN_WORKFLOW_ROWS = 30


async def register_trained_artifact(
    org_id: str,
    *,
    name: str,
    model_type: ModelType,
    base_model: str,
    artifact: bytes,
    metrics: ModelMetrics,
    description: str | None = None,
) -> str | None:
    registry = get_model_registry()
    existing_models = await registry.list_models(org_id=org_id, model_type=model_type)
    existing = next((model for model in existing_models if model.name == name), None)
    if existing:
        model_id = existing.id
    else:
        model = await registry.create_model(
            org_id=org_id,
            name=name,
            model_type=model_type,
            description=description or f"Catalog training artifact for {name}",
            base_model=base_model,
            task_type=INTELLIGENCE_TASK_TYPE,
        )
        model_id = model.id
    try:
        await registry.add_version(model_id=model_id, artifact_data=artifact, metrics=metrics)
        await registry.deploy_version(model_id)
    except ValueError as exc:
        if "BLOB_READ_WRITE_TOKEN" in str(exc):
            logger.warning(
                "catalog_training_artifact_skipped org_id=%s name=%s error=%s",
                org_id,
                name,
                exc,
            )
            return None
        raise
    return model_id


async def train_v2_intent_classifier(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    registry_name: str | None = None,
) -> dict[str, Any]:
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    queries = await collect_query_corpus(active, org_id, since_days=90, client=db)
    texts = [str(row.get("query_text") or "") for row in queries if row.get("query_text")]
    labels = [str(row.get("query_category") or "general") for row in queries if row.get("query_text")]
    if len(texts) < MIN_QUERY_ROWS:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "query_rows": len(texts),
            "required": MIN_QUERY_ROWS,
        }
    classifier = IntentClassifier()
    metrics = await classifier.train_from_text(texts, labels)
    model_id = await register_trained_artifact(
        org_id,
        name=registry_name or CATALOG_MODEL_NAMES["intent_classifier"],
        model_type=ModelType.CLASSIFIER,
        base_model="intent_classifier",
        artifact=classifier.save(),
        metrics=metrics,
    )
    return {
        "trained": model_id is not None,
        "model_id": model_id,
        "query_rows": len(texts),
        "metrics": {
            "training_samples": metrics.training_samples,
            "validation_samples": metrics.validation_samples,
            "accuracy": metrics.accuracy,
            "f1_score": metrics.f1_score,
            "custom_metrics": metrics.custom_metrics,
        },
    }


async def train_v3_query_clusterer(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    persist_clusters: bool = True,
    registry_name: str | None = None,
) -> dict[str, Any]:
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    queries = await collect_query_corpus(active, org_id, since_days=90, client=db)
    distinct_count = distinct_normalized_count(queries)
    if distinct_count < MIN_CLUSTERING_ROWS:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "distinct_queries": distinct_count,
            "required": MIN_CLUSTERING_ROWS,
        }

    unique: dict[str, dict[str, Any]] = {}
    for row in queries:
        text = str(row.get("normalized_query_text") or normalize_query(str(row.get("query_text") or "")))
        if text:
            unique.setdefault(text, row)
    texts = list(unique.keys())
    embeddings = [get_embedding(text, active, org_id=org_id) for text in texts]

    clusterer = QueryClusterer(min_cluster_size=3, min_samples=2)
    metrics = await clusterer.train(embeddings=embeddings, normalized_queries=texts)
    model_id = await register_trained_artifact(
        org_id,
        name=registry_name or CATALOG_MODEL_NAMES["query_clusterer"],
        model_type=ModelType.EMBEDDING,
        base_model="query_clusterer",
        artifact=clusterer.save(),
        metrics=metrics,
    )

    cluster_rows: list[dict[str, Any]] = []
    glossary_rows: list[dict[str, Any]] = []
    if persist_clusters:
        cluster_rows = await run_query_clustering(active, org_id, queries, client=db)
        glossary_rows = await run_glossary_extraction(active, org_id, queries, client=db)

    return {
        "trained": model_id is not None,
        "model_id": model_id,
        "distinct_queries": distinct_count,
        "cluster_count": len(clusterer.cluster_members()),
        "persisted_clusters": len(cluster_rows),
        "glossary_terms": len(glossary_rows),
        "metrics": metrics.custom_metrics,
    }


async def train_v4_memory_promotion_scorer(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    registry_name: str | None = None,
) -> dict[str, Any]:
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    result = (
        db.table("memory_promotion_candidates")
        .select("candidate_type, memory_category, status, frequency, department_count, content")
        .eq("org_id", org_id)
        .execute()
    )
    candidates = list(result.data or [])
    scorer = MemoryPromotionScorer()
    resolved = [
        row
        for row in candidates
        if MemoryPromotionScorer.label_from_status(row.get("status")) is not None
    ]
    if len(resolved) < scorer.MIN_TRAINING_EXAMPLES:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "resolved_candidates": len(resolved),
            "required": scorer.MIN_TRAINING_EXAMPLES,
        }
    metrics = await scorer.train(candidates=resolved)
    model_id = await register_trained_artifact(
        org_id,
        name=registry_name or CATALOG_MODEL_NAMES["memory_promotion_scorer"],
        model_type=ModelType.CLASSIFIER,
        base_model="memory_promotion_scorer",
        artifact=scorer.save(),
        metrics=metrics,
    )
    return {
        "trained": model_id is not None,
        "model_id": model_id,
        "resolved_candidates": len(resolved),
        "metrics": metrics.custom_metrics,
    }


async def train_v5_retrieval_ranker(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    registry_name: str | None = None,
) -> dict[str, Any]:
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    example_count = await count_training_examples(org_id, db)
    if example_count < RetrievalRanker.MIN_TRAINING_EXAMPLES:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "training_examples": example_count,
            "required": RetrievalRanker.MIN_TRAINING_EXAMPLES,
        }
    examples = await collect_training_examples(org_id, db)
    ranker = RetrievalRanker()
    metrics = await ranker.train(examples)
    model_id = await register_trained_artifact(
        org_id,
        name=registry_name or CATALOG_MODEL_NAMES["retrieval_ranker"],
        model_type=ModelType.CLASSIFIER,
        base_model="retrieval_ranker",
        artifact=ranker.save(),
        metrics=metrics,
    )
    return {
        "trained": model_id is not None,
        "model_id": model_id,
        "training_examples": len(examples),
        "learned_reliability_weight": ranker.get_learned_weight(),
        "metrics": metrics.custom_metrics,
    }


async def train_retrieval_memory_learner(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Unified v3 + v4 + v5/v7 training pass."""
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    v3 = await train_v3_query_clusterer(org_id, settings=active, client=db, persist_clusters=True)
    v4 = await train_v4_memory_promotion_scorer(org_id, settings=active, client=db)
    v5 = await train_v5_retrieval_ranker(org_id, settings=active, client=db)
    any_trained = any(result.get("trained") for result in (v3, v4, v5))
    return {
        "trained": any_trained,
        "components": {
            "query_clusterer_v3": v3,
            "memory_promotion_v4": v4,
            "retrieval_ranker_v5": v5,
        },
    }


async def train_workflow_anomaly_detector(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    workflow_features = collect_workflow_run_features(active, org_id, since_days=30, client=db)
    if len(workflow_features) < MIN_WORKFLOW_ROWS:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "workflow_rows": len(workflow_features),
            "required": MIN_WORKFLOW_ROWS,
        }
    detector = AnomalyDetector(contamination=active.ml_anomaly_contamination)
    metrics = await detector.train(features_to_anomaly_input(workflow_features))
    model_id = await register_trained_artifact(
        org_id,
        name=CATALOG_MODEL_NAMES["workflow_anomaly_detector"],
        model_type=ModelType.ANOMALY_DETECTOR,
        base_model="anomaly_detector",
        artifact=detector.save(),
        metrics=metrics,
    )
    return {"trained": model_id is not None, "model_id": model_id, "workflow_rows": len(workflow_features)}


async def train_workflow_duration_forecaster(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    workflow_features = collect_workflow_run_features(active, org_id, since_days=30, client=db)
    x_rows, y_values = features_to_forecaster_train(workflow_features)
    if len(x_rows) < MIN_WORKFLOW_ROWS:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "workflow_rows": len(x_rows),
            "required": MIN_WORKFLOW_ROWS,
        }
    forecaster = WorkflowForecaster(
        target="duration_ms",
        algorithm="gradient_boosting",
        forecast_horizon=active.ml_forecast_horizon,
    )
    metrics = await forecaster.train(x_rows, y_values)
    model_id = await register_trained_artifact(
        org_id,
        name=CATALOG_MODEL_NAMES["workflow_duration_forecaster"],
        model_type=ModelType.FORECASTER,
        base_model="forecaster",
        artifact=forecaster.save(),
        metrics=metrics,
    )
    return {"trained": model_id is not None, "model_id": model_id, "workflow_rows": len(x_rows)}


async def train_workflow_success_predictor(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    workflow_features = collect_workflow_run_features(active, org_id, since_days=30, client=db)
    x_rows, y_values = features_to_success_train(workflow_features)
    if len(x_rows) < MIN_WORKFLOW_ROWS:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "workflow_rows": len(x_rows),
            "required": MIN_WORKFLOW_ROWS,
        }
    predictor = WorkflowSuccessPredictor()
    metrics = await predictor.train(x_rows, y_values)
    model_id = await register_trained_artifact(
        org_id,
        name=CATALOG_MODEL_NAMES["workflow_success_predictor"],
        model_type=ModelType.CLASSIFIER,
        base_model="success_predictor",
        artifact=predictor.save(),
        metrics=metrics,
    )
    return {"trained": model_id is not None, "model_id": model_id, "workflow_rows": len(x_rows)}


async def train_revenue_forecaster(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    from app.ml.revenue_forecasting import RevenueForecaster

    active = settings or get_settings()
    db = client or get_supabase_client(active)
    since = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    rows = (
        db.table("agent_action_outcomes")
        .select("metric_value, recorded_at")
        .eq("org_id", org_id)
        .gte("recorded_at", since)
        .order("recorded_at")
        .execute()
        .data
        or []
    )
    series = [{"value": float(row.get("metric_value") or 0)} for row in rows if row.get("metric_value") is not None]
    forecaster = RevenueForecaster()
    if len(series) < forecaster.MIN_HISTORY_POINTS:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "data_points": len(series),
            "required": forecaster.MIN_HISTORY_POINTS,
        }
    metrics = await forecaster.train([], time_series=series)
    model_id = await register_trained_artifact(
        org_id,
        name=CATALOG_MODEL_NAMES["revenue_forecaster"],
        model_type=ModelType.REGRESSOR,
        base_model="revenue_forecaster",
        artifact=forecaster.save(),
        metrics=metrics,
    )
    return {"trained": model_id is not None, "model_id": model_id, "data_points": len(series)}


async def train_churn_risk_scorer(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    from app.ml.churn_feature_ingest import list_churn_training_rows
    from app.ml.churn_scoring import ChurnRiskScorer

    active = settings or get_settings()
    db = client or get_supabase_client(active)
    # Prefer explicit churn_customer_signal rows (FEATURE_KEYS + label contract).
    labeled = list_churn_training_rows(db, org_id)
    features = [row["features"] for row in labeled]
    labels = [1 if row["churned"] else 0 for row in labeled]
    scorer = ChurnRiskScorer()
    if len(features) < scorer.MIN_TRAINING_EXAMPLES:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "training_examples": len(features),
            "required": scorer.MIN_TRAINING_EXAMPLES,
            "metric_name": "churn_customer_signal",
            "note": "Need labeled churn_customer_signal rows via churn_feature_ingest.",
        }
    metrics = await scorer.train(features, labels)
    model_id = await register_trained_artifact(
        org_id,
        name=CATALOG_MODEL_NAMES["churn_risk_scorer"],
        model_type=ModelType.CLASSIFIER,
        base_model="churn_risk_scorer",
        artifact=scorer.save(),
        metrics=metrics,
    )
    return {"trained": model_id is not None, "model_id": model_id, "training_examples": len(features)}


async def train_cf_matrix_factorizer(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Train TruncatedSVD user×item factors for CF soft-rank (advisory only)."""
    from app.ml.cf_interaction_ingest import (
        load_scored_interactions,
        matrix_factorization_gate_status,
    )
    from app.ml.cf_matrix_factorization import CfMatrixFactorizer

    active = settings or get_settings()
    db = client or get_supabase_client(active)
    gate = matrix_factorization_gate_status(db, org_id)
    if not gate.get("ready"):
        return {
            "trained": False,
            "reason": "insufficient_data",
            "gate": gate,
            "note": "Need ≥50 scored interactions, ≥2 actors, ≥3 items in 30d.",
        }
    interactions = load_scored_interactions(db, org_id)
    factorizer = CfMatrixFactorizer()
    metrics = await factorizer.train(interactions=interactions)
    model_id = await register_trained_artifact(
        org_id,
        name=CATALOG_MODEL_NAMES["cf_matrix_factorizer"],
        model_type=ModelType.EMBEDDING,
        base_model="cf_matrix_factorizer",
        artifact=factorizer.save(),
        metrics=metrics,
        description="CF TruncatedSVD matrix factorization for heuristic soft-rank",
    )
    return {
        "trained": model_id is not None,
        "model_id": model_id,
        "training_examples": len(interactions),
        "gate": gate,
        "method": "truncated_svd",
        "metrics": {
            "n_users": (metrics.custom_metrics or {}).get("n_users"),
            "n_items": (metrics.custom_metrics or {}).get("n_items"),
            "n_components": (metrics.custom_metrics or {}).get("n_components"),
            "rmse": (metrics.custom_metrics or {}).get("rmse"),
            "explained_variance": (metrics.custom_metrics or {}).get("explained_variance"),
        },
    }


def _payload_features(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, float]:
    payload = row.get("outcome_payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    return {key: float(payload.get(key) or row.get(key) or 0.0) for key in keys}


async def train_sla_breach_predictor(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    from app.ml.predictive_ops_models import SLA_FEATURE_KEYS, SlaBreachPredictor

    active = settings or get_settings()
    db = client or get_supabase_client(active)
    rows = (
        db.table("agent_action_outcomes")
        .select("outcome_payload, outcome_success, after_value")
        .eq("org_id", org_id)
        .eq("metric_name", "ticket_volume")
        .execute()
        .data
        or []
    )
    features: list[dict[str, float]] = []
    labels: list[int] = []
    for row in rows:
        feature_row = _payload_features(row, SLA_FEATURE_KEYS)
        if not any(feature_row.values()) and row.get("after_value") is not None:
            feature_row["open_tickets"] = float(row.get("after_value") or 0)
        if not any(feature_row.values()):
            continue
        payload = row.get("outcome_payload") or {}
        breached = payload.get("sla_breached") if isinstance(payload, dict) else None
        label = bool(breached) if breached is not None else not bool(row.get("outcome_success", True))
        features.append(feature_row)
        labels.append(1 if label else 0)
    predictor = SlaBreachPredictor()
    if len(features) < predictor.MIN_TRAINING_EXAMPLES:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "training_examples": len(features),
            "required": predictor.MIN_TRAINING_EXAMPLES,
        }
    metrics = await predictor.train(features, labels)
    model_id = await register_trained_artifact(
        org_id,
        name=CATALOG_MODEL_NAMES["sla_breach_predictor"],
        model_type=ModelType.CLASSIFIER,
        base_model="sla_breach_predictor",
        artifact=predictor.save(),
        metrics=metrics,
    )
    return {"trained": model_id is not None, "model_id": model_id, "training_examples": len(features)}


async def train_deal_loss_scorer(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    from app.ml.predictive_ops_models import DEAL_FEATURE_KEYS, DealLossScorer

    active = settings or get_settings()
    db = client or get_supabase_client(active)
    rows = (
        db.table("agent_action_outcomes")
        .select("outcome_payload, outcome_success")
        .eq("org_id", org_id)
        .eq("target_entity_type", "deal")
        .not_.is_("measured_at", "null")
        .execute()
        .data
        or []
    )
    features: list[dict[str, float]] = []
    labels: list[int] = []
    for row in rows:
        feature_row = _payload_features(row, DEAL_FEATURE_KEYS)
        if not any(feature_row.values()):
            continue
        lost = not bool(row.get("outcome_success"))
        features.append(feature_row)
        labels.append(1 if lost else 0)
    scorer = DealLossScorer()
    if len(features) < scorer.MIN_TRAINING_EXAMPLES:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "training_examples": len(features),
            "required": scorer.MIN_TRAINING_EXAMPLES,
        }
    metrics = await scorer.train(features, labels)
    model_id = await register_trained_artifact(
        org_id,
        name=CATALOG_MODEL_NAMES["deal_loss_scorer"],
        model_type=ModelType.CLASSIFIER,
        base_model="deal_loss_scorer",
        artifact=scorer.save(),
        metrics=metrics,
    )
    return {"trained": model_id is not None, "model_id": model_id, "training_examples": len(features)}


async def train_capacity_forecaster(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    from app.ml.predictive_ops_models import CapacityForecaster

    active = settings or get_settings()
    db = client or get_supabase_client(active)
    rows = (
        db.table("agent_action_outcomes")
        .select("after_value, measured_at")
        .eq("org_id", org_id)
        .eq("metric_name", "ticket_volume")
        .order("measured_at")
        .execute()
        .data
        or []
    )
    series = [
        {"value": float(row.get("after_value") or 0)}
        for row in rows
        if row.get("after_value") is not None
    ]
    forecaster = CapacityForecaster()
    if len(series) < forecaster.MIN_TRAINING_EXAMPLES:
        return {
            "trained": False,
            "reason": "insufficient_data",
            "training_examples": len(series),
            "required": forecaster.MIN_TRAINING_EXAMPLES,
        }
    metrics = await forecaster.train([], time_series=series)
    model_id = await register_trained_artifact(
        org_id,
        name=CATALOG_MODEL_NAMES["capacity_forecaster"],
        model_type=ModelType.REGRESSOR,
        base_model="capacity_forecaster",
        artifact=forecaster.save(),
        metrics=metrics,
    )
    return {"trained": model_id is not None, "model_id": model_id, "training_examples": len(series)}


    return {"trained": model_id is not None, "model_id": model_id, "training_examples": len(series)}


async def sync_retrieval_ranker_examples(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Mirror rag_chunk_outcomes into retrieval_ranker_examples for admin metrics parity."""
    active = settings or get_settings()
    db = client or get_supabase_client(active)
    rag_count = await count_training_examples(org_id, db)
    synced = 0
    try:
        rows = (
            db.table("rag_chunk_outcomes")
            .select("chunk_id, message_id, outcome_helpful, recorded_at")
            .eq("org_id", org_id)
            .not_.is_("outcome_helpful", "null")
            .order("recorded_at", desc=True)
            .limit(500)
            .execute()
            .data
            or []
        )
        for row in rows:
            label = 1 if row.get("outcome_helpful") else 0
            payload = {
                "id": str(uuid4()),
                "org_id": org_id,
                "chunk_id": row.get("chunk_id"),
                "message_id": row.get("message_id"),
                "query_text": str(row.get("message_id") or row.get("chunk_id") or ""),
                "relevance_label": label,
                "created_at": row.get("recorded_at") or datetime.now(timezone.utc).isoformat(),
            }
            try:
                db.table("retrieval_ranker_examples").upsert(payload, on_conflict="org_id,chunk_id,message_id").execute()
                synced += 1
            except Exception:  # noqa: BLE001
                try:
                    db.table("retrieval_ranker_examples").insert(payload).execute()
                    synced += 1
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        return {"example_count": rag_count, "synced_rows": 0, "source": "rag_chunk_outcomes_only"}
    return {
        "example_count": max(rag_count, synced),
        "synced_rows": synced,
        "rag_chunk_outcomes": rag_count,
        "source": "rag_chunk_outcomes",
    }


async def train_causal_impact_analyzer(
    org_id: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    from app.ml.causal_analysis import CausalImpactAnalyzer

    active = settings or get_settings()
    analyzer = CausalImpactAnalyzer()
    structured = await analyzer.predict_structured(org_id=org_id, metric_name="deal_amount", settings=active)
    if structured.get("status") != "ok":
        return {"trained": False, **structured}
    metrics = ModelMetrics(
        accuracy=float(structured.get("confidence") or 0.5),
        custom_metrics={
            "sample_size": structured.get("sample_size"),
            "estimated_effect": structured.get("estimated_effect"),
            "method": structured.get("method"),
        },
    )
    model_id = await register_trained_artifact(
        org_id,
        name="catalog-causal-impact",
        model_type=ModelType.CAUSAL_MODEL,
        base_model="causal_impact_analyzer",
        artifact=str(structured).encode("utf-8"),
        metrics=metrics,
        description="Org-scoped pre/post causal impact analyzer",
    )
    return {"trained": model_id is not None, "model_id": model_id, **structured}


TRAINING_DISPATCH: dict[str, Any] = {
    "intent_classifier": train_v2_intent_classifier,
    "query_clusterer": train_v3_query_clusterer,
    "memory_promotion_scorer": train_v4_memory_promotion_scorer,
    "retrieval_ranker": train_v5_retrieval_ranker,
    "retrieval_memory_learner": train_retrieval_memory_learner,
    "workflow_anomaly_detector": train_workflow_anomaly_detector,
    "workflow_duration_forecaster": train_workflow_duration_forecaster,
    "workflow_success_predictor": train_workflow_success_predictor,
    "revenue_forecaster": train_revenue_forecaster,
    "churn_risk_scorer": train_churn_risk_scorer,
    "cf_matrix_factorizer": train_cf_matrix_factorizer,
    "sla_breach_predictor": train_sla_breach_predictor,
    "deal_loss_scorer": train_deal_loss_scorer,
    "capacity_forecaster": train_capacity_forecaster,
    "causal_impact_analyzer": train_causal_impact_analyzer,
}


async def train_catalog_model(
    org_id: str,
    model_name: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    trainer = TRAINING_DISPATCH.get(model_name)
    if trainer is None:
        raise ValueError(f"No training pipeline registered for {model_name}")
    active = settings or get_settings()
    result = await trainer(org_id, settings=active)
    return {"model_name": model_name, "org_id": org_id, **result}
