"""Per-org company intelligence learning loop orchestrator."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.anomaly import AnomalyDetector
from app.ml.base import ModelMetrics, ModelType
from app.ml.classifiers import IntentClassifier
from app.ml.feature_extraction import (
    collect_workflow_run_features,
    features_to_anomaly_input,
    features_to_forecaster_train,
    features_to_success_train,
)
from app.ml.forecasting import WorkflowForecaster, WorkflowSuccessPredictor
from app.ml.registry import get_model_registry
from app.services.company_intelligence_collectors import (
    aggregate_query_categories,
    collect_org_memory_digest,
    collect_query_corpus,
    fetch_active_workflow_definitions,
)
from app.services.company_intelligence_synthesis import synthesize_company_intelligence
from app.ml.learning_to_rank import (
    RETRIEVAL_RANKER_MODEL_NAME,
    RetrievalRanker,
    collect_training_examples,
    count_training_examples,
)
from app.ml.registry import get_model_registry
from app.services.entity_relationship_builder import rebuild_org_entity_relationships
from app.services.knowledge_intelligence_service import (
    distinct_normalized_count,
    identify_knowledge_gaps,
    run_glossary_extraction,
    run_query_clustering,
)
from app.services.user_intelligence import UserIntelligenceService
from app.services.response_evaluation_service import consolidate_recent
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

COMPANY_MODEL_NAMES = {
    "intent": "company-query-intent",
    "anomaly": "company-workflow-anomaly",
    "forecaster": "company-workflow-duration-forecast",
    "success": "company-workflow-success",
    "retrieval_ranker": RETRIEVAL_RANKER_MODEL_NAME,
}


class CompanyIntelligenceOrchestrator:
    """Connects existing ML primitives into a closed per-org learning loop."""

    SNAPSHOT_TASK_TYPE = "company_intelligence"
    MIN_QUERY_ROWS = 50
    MIN_WORKFLOW_ROWS = 30
    MIN_CLUSTERING_ROWS = 40
    STALE_HOURS = 36

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def run_for_org(self, org_id: str) -> dict[str, Any]:
        run_id = await self._start_run_log(org_id)
        client = self._client()
        try:
            queries = await collect_query_corpus(self.settings, org_id, since_days=90, client=client)
            workflow_features = collect_workflow_run_features(
                self.settings, org_id, since_days=30, client=client
            )
            memories = await collect_org_memory_digest(self.settings, org_id, client=client)

            intent_model_id = None
            if len(queries) >= self.MIN_QUERY_ROWS:
                intent_model_id = await self._train_intent_classifier(org_id, queries)

            anomaly_model_id = None
            recent_anomalies: list[dict[str, Any]] = []
            if len(workflow_features) >= self.MIN_WORKFLOW_ROWS:
                anomaly_model_id, recent_anomalies = await self._train_anomaly_detector(
                    org_id, workflow_features
                )

            forecaster_model_id = None
            forecast_summary: list[dict[str, Any]] | None = None
            if len(workflow_features) >= self.MIN_WORKFLOW_ROWS:
                forecaster_model_id, forecast_summary = await self._train_forecaster(
                    org_id, workflow_features
                )

            success_model_id = None
            success_predictions: list[dict[str, Any]] | None = None
            if len(workflow_features) >= self.MIN_WORKFLOW_ROWS:
                success_model_id, success_predictions = await self._train_success_predictor(
                    org_id, workflow_features, client
                )

            cluster_results: list[dict[str, Any]] | None = None
            if distinct_normalized_count(queries) >= self.MIN_CLUSTERING_ROWS:
                cluster_results = await run_query_clustering(
                    self.settings, org_id, queries, client=client
                )

            glossary_results = await run_glossary_extraction(
                self.settings, org_id, queries, client=client
            )

            knowledge_gaps = await identify_knowledge_gaps(
                self.settings,
                org_id,
                cluster_results,
                client=client,
            )

            relationship_summary = await rebuild_org_entity_relationships(
                org_id, settings=self.settings, client=client
            )

            evaluations_consolidated = await consolidate_recent(
                self.settings, org_id, since_days=1, client=client
            )

            ranker_model_id = None
            training_count = await count_training_examples(org_id, client)
            if training_count >= RetrievalRanker.MIN_TRAINING_EXAMPLES:
                ranker_model_id = await self._train_retrieval_ranker(org_id, client)

            category_distribution = aggregate_query_categories(queries)
            org_deltas = await UserIntelligenceService()._get_changes_since(client, org_id)
            context_markdown = synthesize_company_intelligence(
                category_distribution=category_distribution,
                recent_anomalies=recent_anomalies,
                forecast_summary=forecast_summary,
                success_predictions=success_predictions,
                memory_digest=memories,
                org_deltas=org_deltas,
                knowledge_gaps=knowledge_gaps,
                glossary_terms=glossary_results,
            )

            await self._upsert_snapshot(
                org_id,
                context_markdown,
                intent_model_id=intent_model_id,
                anomaly_model_id=anomaly_model_id,
                forecaster_model_id=forecaster_model_id,
                success_model_id=success_model_id,
                source_counts={
                    "query_rows": len(queries),
                    "workflow_rows": len(workflow_features),
                    "memory_rows": len(memories),
                },
                signals={
                    "category_distribution": category_distribution,
                    "anomaly_count": sum(1 for a in recent_anomalies if a.get("is_anomaly")),
                    "cluster_count": len(cluster_results or []),
                    "glossary_count": len(glossary_results or []),
                    "knowledge_gap_count": len(knowledge_gaps or []),
                    "entity_relationship_count": relationship_summary.get("total", 0),
                    "evaluation_count": len(evaluations_consolidated),
                    "retrieval_ranker_trained": ranker_model_id is not None,
                },
            )

            stats = {
                "query_rows": len(queries),
                "workflow_rows": len(workflow_features),
                "memory_rows": len(memories),
                "intent_model_id": intent_model_id,
                "anomaly_model_id": anomaly_model_id,
                "forecaster_model_id": forecaster_model_id,
                "success_model_id": success_model_id,
                "ranker_model_id": ranker_model_id,
                "evaluations_consolidated": len(evaluations_consolidated),
                "snapshot_chars": len(context_markdown),
                "cluster_count": len(cluster_results or []),
                "glossary_count": len(glossary_results or []),
                "knowledge_gap_count": len(knowledge_gaps or []),
                "entity_relationship_count": relationship_summary.get("total", 0),
            }
            await self._complete_run_log(run_id, status="completed", stats=stats)
            logger.info("company_intelligence_completed org_id=%s stats=%s", org_id, stats)
            return {"org_id": org_id, **stats}
        except Exception as exc:
            await self._complete_run_log(run_id, status="failed", error=str(exc))
            logger.error("company_intelligence_failed org_id=%s error=%s", org_id, exc)
            raise

    async def get_context_for_prompt(self, org_id: str) -> str:
        try:
            row = await self._load_latest_snapshot(org_id)
            if not row or self._is_stale(row):
                return ""
            markdown = str(row.get("context_markdown") or "").strip()
            if not markdown:
                return ""
            updated = row.get("updated_at")
            if updated:
                markdown = f"{markdown}\n\n(Company intelligence last updated: {updated})"
            return markdown[:4200]
        except Exception as exc:  # noqa: BLE001
            logger.debug("company_intelligence_prompt_load_skipped org_id=%s error=%s", org_id, exc)
            return ""

    async def _train_intent_classifier(self, org_id: str, queries: list[dict[str, Any]]) -> str | None:
        texts = [str(row.get("query_text") or "") for row in queries if row.get("query_text")]
        labels = [str(row.get("query_category") or "general") for row in queries if row.get("query_text")]
        if len(texts) < self.MIN_QUERY_ROWS:
            return None
        classifier = IntentClassifier()
        metrics = await classifier.train_from_text(texts, labels)
        return await self._register_or_update_model(
            org_id,
            name=COMPANY_MODEL_NAMES["intent"],
            model_type=ModelType.CLASSIFIER,
            base_model="intent_classifier",
            artifact=classifier.save(),
            metrics=metrics,
        )

    async def _train_anomaly_detector(
        self,
        org_id: str,
        workflow_features: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        detector = AnomalyDetector(contamination=self.settings.ml_anomaly_contamination)
        metrics = await detector.train(features_to_anomaly_input(workflow_features))
        model_id = await self._register_or_update_model(
            org_id,
            name=COMPANY_MODEL_NAMES["anomaly"],
            model_type=ModelType.ANOMALY_DETECTOR,
            base_model="anomaly_detector",
            artifact=detector.save(),
            metrics=metrics,
        )
        recent = features_to_anomaly_input(workflow_features[-7:])
        anomalies = await detector.detect_workflow_anomalies(recent) if recent else []
        return model_id, anomalies

    async def _train_forecaster(
        self,
        org_id: str,
        workflow_features: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]] | None]:
        x_rows, y_values = features_to_forecaster_train(workflow_features)
        if len(x_rows) < self.MIN_WORKFLOW_ROWS:
            return None, None
        forecaster = WorkflowForecaster(
            target="duration_ms",
            algorithm="gradient_boosting",
            forecast_horizon=self.settings.ml_forecast_horizon,
        )
        metrics = await forecaster.train(x_rows, y_values)
        model_id = await self._register_or_update_model(
            org_id,
            name=COMPANY_MODEL_NAMES["forecaster"],
            model_type=ModelType.FORECASTER,
            base_model="forecaster",
            artifact=forecaster.save(),
            metrics=metrics,
        )
        summary = await self._summarize_forecast(forecaster, x_rows[-1:] if x_rows else [])
        return model_id, summary

    async def _train_success_predictor(
        self,
        org_id: str,
        workflow_features: list[dict[str, Any]],
        client: Any,
    ) -> tuple[str | None, list[dict[str, Any]] | None]:
        x_rows, y_values = features_to_success_train(workflow_features)
        if len(x_rows) < self.MIN_WORKFLOW_ROWS:
            return None, None
        predictor = WorkflowSuccessPredictor()
        metrics = await predictor.train(x_rows, y_values)
        model_id = await self._register_or_update_model(
            org_id,
            name=COMPANY_MODEL_NAMES["success"],
            model_type=ModelType.CLASSIFIER,
            base_model="success_predictor",
            artifact=predictor.save(),
            metrics=metrics,
        )
        predictions = await self._predict_active_workflow_risk(predictor, org_id, client)
        return model_id, predictions

    async def _summarize_forecast(
        self,
        forecaster: WorkflowForecaster,
        recent_features: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not recent_features:
            return []
        sample = recent_features[-3:] if len(recent_features) >= 3 else recent_features
        predictions, intervals = await forecaster.predict(sample, return_probabilities=True)
        intervals = intervals or []
        now = datetime.now(timezone.utc)
        summary: list[dict[str, Any]] = []
        for idx, (pred, interval) in enumerate(zip(predictions, intervals)):
            ts = (now + timedelta(days=idx + 1)).isoformat()
            summary.append(
                {
                    "timestamp": ts,
                    "predicted_duration_ms": pred,
                    "confidence_interval": interval,
                }
            )
        return summary

    async def _predict_active_workflow_risk(
        self,
        predictor: WorkflowSuccessPredictor,
        org_id: str,
        client: Any,
    ) -> list[dict[str, Any]]:
        from app.ml.feature_extraction import extract_features_for_run

        active = await fetch_active_workflow_definitions(self.settings, org_id, client=client)
        if not active:
            return []
        predictions: list[dict[str, Any]] = []
        for item in active[:10]:
            wf_id = str(item.get("workflow_id") or "")
            snapshot = item.get("definition_snapshot")
            if not isinstance(snapshot, dict):
                continue
            feat = extract_features_for_run(
                {"workflow_id": wf_id, "status": "running", "created_at": datetime.now(timezone.utc).isoformat()},
                [],
                snapshot,
            )
            x_row = feat.to_ml_dict(include_targets=False)
            result = (await predictor.predict_success([x_row]))[0]
            result["workflow_id"] = wf_id
            predictions.append(result)
        return sorted(predictions, key=lambda row: float(row.get("success_probability") or 1.0))

    async def _train_retrieval_ranker(self, org_id: str, client: Any) -> str | None:
        examples = await collect_training_examples(org_id, client)
        if len(examples) < RetrievalRanker.MIN_TRAINING_EXAMPLES:
            return None
        ranker = RetrievalRanker()
        metrics = await ranker.train(examples)
        return await self._register_or_update_model(
            org_id,
            name=COMPANY_MODEL_NAMES["retrieval_ranker"],
            model_type=ModelType.CLASSIFIER,
            base_model="retrieval_ranker",
            artifact=ranker.save(),
            metrics=metrics,
        )

    async def _register_or_update_model(
        self,
        org_id: str,
        *,
        name: str,
        model_type: ModelType,
        base_model: str,
        artifact: bytes,
        metrics: ModelMetrics,
    ) -> str:
        registry = get_model_registry()
        existing_models = await registry.list_models(org_id=org_id, model_type=model_type)
        existing = next((m for m in existing_models if m.name == name), None)
        if existing:
            model_id = existing.id
        else:
            model = await registry.create_model(
                org_id=org_id,
                name=name,
                model_type=model_type,
                description=f"Company intelligence {name}",
                base_model=base_model,
                task_type=self.SNAPSHOT_TASK_TYPE,
            )
            model_id = model.id
        try:
            await registry.add_version(model_id=model_id, artifact_data=artifact, metrics=metrics)
            await registry.deploy_version(model_id)
        except ValueError as exc:
            if "BLOB_READ_WRITE_TOKEN" in str(exc):
                logger.warning(
                    "company_intelligence_model_artifact_skipped org_id=%s name=%s error=%s",
                    org_id,
                    name,
                    exc,
                )
                return None
            raise
        return model_id

    async def _start_run_log(self, org_id: str) -> str:
        client = self._client()
        result = (
            client.table("org_intelligence_runs")
            .insert({"org_id": org_id, "status": "running"})
            .execute()
        )
        if not result.data:
            raise RuntimeError("Failed to create org_intelligence_runs row")
        return str(result.data[0]["id"])

    async def _complete_run_log(
        self,
        run_id: str,
        *,
        status: str,
        stats: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        client = self._client()
        payload: dict[str, Any] = {
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if stats is not None:
            payload["stats_json"] = stats
        if error:
            payload["error"] = error[:2000]
        client.table("org_intelligence_runs").update(payload).eq("id", run_id).execute()

    async def _upsert_snapshot(
        self,
        org_id: str,
        context_markdown: str,
        *,
        intent_model_id: str | None,
        anomaly_model_id: str | None,
        forecaster_model_id: str | None,
        success_model_id: str | None,
        source_counts: dict[str, Any],
        signals: dict[str, Any],
    ) -> None:
        client = self._client()
        now = datetime.now(timezone.utc).isoformat()
        client.table("org_intelligence_snapshots").upsert(
            {
                "org_id": org_id,
                "context_markdown": context_markdown,
                "signals_json": signals,
                "intent_model_id": intent_model_id,
                "anomaly_model_id": anomaly_model_id,
                "forecaster_model_id": forecaster_model_id,
                "success_model_id": success_model_id,
                "source_counts": source_counts,
                "updated_at": now,
            }
        ).execute()

    async def _load_latest_snapshot(self, org_id: str) -> dict[str, Any] | None:
        client = self._client()
        result = (
            client.table("org_intelligence_snapshots")
            .select("*")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return result.data[0]

    def _is_stale(self, row: dict[str, Any]) -> bool:
        updated = row.get("updated_at")
        if not updated:
            return True
        try:
            updated_at = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return True
        return datetime.now(timezone.utc) - updated_at > timedelta(hours=self.STALE_HOURS)


_orchestrator: CompanyIntelligenceOrchestrator | None = None


def get_company_intelligence_orchestrator() -> CompanyIntelligenceOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CompanyIntelligenceOrchestrator()
    return _orchestrator


def run_company_intelligence_for_org_sync(org_id: str, settings: Settings | None = None) -> dict[str, Any]:
    """Sync wrapper for scheduler thread execution."""
    import asyncio

    orchestrator = CompanyIntelligenceOrchestrator(settings=settings)
    return asyncio.run(orchestrator.run_for_org(org_id))
