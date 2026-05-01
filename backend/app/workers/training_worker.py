"""Background worker for processing training jobs."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from app.config import get_settings
from app.core.logging import get_logger
from app.ml.anomaly import AnomalyDetector
from app.ml.base import ModelMetrics, ModelType
from app.ml.classifiers import IntentClassifier, SklearnClassifier
from app.ml.fine_tuning import FineTunedLLM, FineTuningConfig, convert_dataset_to_examples
from app.ml.forecasting import WorkflowForecaster
from app.ml.registry import get_model_registry
from app.workers.queue import dequeue_training_job
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class TrainingWorker:
    """Processes training jobs from the queue."""

    def __init__(self):
        self._settings = None
        self._running = False
        self._current_job_id: str | None = None

    @property
    def settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_client(self):
        return get_supabase_client(self.settings)

    async def process_job(self, job_id: str) -> None:
        client = self._get_client()
        registry = get_model_registry()
        self._current_job_id = job_id
        try:
            result = client.table("training_jobs").select("*").eq("id", job_id).execute()
            if not result.data:
                logger.error("job_not_found job_id=%s", job_id)
                return
            job = result.data[0]
            client.table("training_jobs").update(
                {"status": "training", "started_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", job_id).execute()

            dataset_result = client.table("training_datasets").select("*").eq("id", job["dataset_id"]).execute()
            if not dataset_result.data:
                raise ValueError(f"Dataset {job['dataset_id']} not found")
            dataset = dataset_result.data[0]
            records_result = client.table("training_records").select("*").eq("dataset_id", job["dataset_id"]).execute()
            records = records_result.data or []
            if not records:
                raise ValueError("No training records found")

            model_base = (job["model_base"] or "").strip()
            metrics: ModelMetrics | None = None
            model_artifact: bytes | None = None
            model_type: ModelType
            if model_base.startswith("gpt-") or model_base.startswith("ft:"):
                model_type = ModelType.FINE_TUNED_LLM
                metrics, model_artifact = await self._train_fine_tuned(job, dataset, records)
            elif model_base in ["classifier", "random_forest", "xgboost", "logistic", "gradient_boosting"]:
                model_type = ModelType.CLASSIFIER
                metrics, model_artifact = await self._train_classifier(job, dataset, records, classifier_type=model_base)
            elif model_base == "intent_classifier":
                model_type = ModelType.CLASSIFIER
                metrics, model_artifact = await self._train_intent_classifier(job, dataset, records)
            elif model_base == "anomaly_detector":
                model_type = ModelType.ANOMALY_DETECTOR
                metrics, model_artifact = await self._train_anomaly_detector(job, dataset, records)
            elif model_base == "forecaster":
                model_type = ModelType.FORECASTER
                metrics, model_artifact = await self._train_forecaster(job, dataset, records)
            else:
                raise ValueError(f"Unknown model base: {model_base}")

            model_name = f"{dataset['name']}_{model_base}"
            existing_models = await registry.list_models(org_id=job["org_id"], model_type=model_type)
            existing = next((m for m in existing_models if m.dataset_id == job["dataset_id"]), None)
            if existing:
                model_id = existing.id
            else:
                model = await registry.create_model(
                    org_id=job["org_id"],
                    name=model_name,
                    model_type=model_type,
                    description=f"Trained from dataset: {dataset['name']}",
                    dataset_id=job["dataset_id"],
                    base_model=model_base,
                    created_by=job["created_by"],
                )
                model_id = model.id
            if model_artifact:
                await registry.add_version(
                    model_id=model_id, artifact_data=model_artifact, metrics=metrics, created_by=job["created_by"]
                )

            client.table("training_jobs").update(
                {
                    "status": "completed",
                    "progress": 100,
                    "metrics": metrics.model_dump() if metrics else {},
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", job_id).execute()
            logger.info("training_job_completed job_id=%s model_base=%s", job_id, model_base)
        except Exception as exc:
            logger.error("training_job_failed job_id=%s error=%s", job_id, str(exc))
            client.table("training_jobs").update(
                {"status": "failed", "error": str(exc), "completed_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", job_id).execute()
        finally:
            self._current_job_id = None

    async def _train_fine_tuned(
        self,
        job: dict,
        dataset: dict,
        records: list[dict],
    ) -> tuple[ModelMetrics, bytes]:
        system_prompt = (dataset.get("metadata") or {}).get("system_prompt")
        examples = convert_dataset_to_examples(records, system_prompt)
        config = FineTuningConfig(base_model=job["model_base"], suffix=f"gravitre-{job['org_id'][:8]}")
        model = FineTunedLLM(config)
        await model.train(examples=examples)
        client = self._get_client()
        while True:
            status = await model.get_job_status()
            progress = 50 if status["status"] == "running" else 0
            if status["status"] == "succeeded":
                progress = 100
            elif status["status"] == "failed":
                raise ValueError(f"Fine-tuning failed: {status['error']}")
            client.table("training_jobs").update({"progress": progress, "metrics": {"openai_status": status["status"]}}).eq(
                "id", job["id"]
            ).execute()
            if status["status"] in ["succeeded", "failed"]:
                break
            await asyncio.sleep(30)
        metrics = await model.get_training_metrics()
        artifact = model.save()
        return metrics, artifact

    async def _train_classifier(
        self,
        job: dict,
        dataset: dict,
        records: list[dict],
        classifier_type: str = "random_forest",
    ) -> tuple[ModelMetrics, bytes]:
        _ = job, dataset
        X: list[dict] = []
        y: list[str] = []
        for record in records:
            try:
                features = json.loads(record["input"])
            except Exception:
                features = {"text": record["input"]}
            X.append(features)
            y.append(record["expected_output"])
        classifier = SklearnClassifier(classifier_type=classifier_type if classifier_type != "classifier" else "random_forest")
        metrics = await classifier.train(X, y)
        return metrics, classifier.save()

    async def _train_intent_classifier(self, job: dict, dataset: dict, records: list[dict]) -> tuple[ModelMetrics, bytes]:
        _ = job, dataset
        texts = [r["input"] for r in records]
        labels = [r["expected_output"] for r in records]
        classifier = IntentClassifier()
        metrics = await classifier.train_from_text(texts, labels)
        return metrics, classifier.save()

    async def _train_anomaly_detector(self, job: dict, dataset: dict, records: list[dict]) -> tuple[ModelMetrics, bytes]:
        _ = job, dataset
        X: list[dict] = []
        for record in records:
            try:
                features = json.loads(record["input"])
            except Exception:
                features = {"value": float(record["input"])}
            X.append(features)
        detector = AnomalyDetector(contamination=self.settings.ml_anomaly_contamination)
        metrics = await detector.train(X)
        return metrics, detector.save()

    async def _train_forecaster(self, job: dict, dataset: dict, records: list[dict]) -> tuple[ModelMetrics, bytes]:
        _ = job, dataset
        X: list[dict] = []
        y: list[float] = []
        for record in records:
            try:
                features = json.loads(record["input"])
            except Exception:
                features = {}
            X.append(features)
            y.append(float(record["expected_output"]))
        forecaster = WorkflowForecaster(forecast_horizon=self.settings.ml_forecast_horizon)
        metrics = await forecaster.train(X, y)
        return metrics, forecaster.save()

    async def poll_queue(self, interval: int = 5) -> None:
        self._running = True
        logger.info("training_worker_started")
        while self._running:
            try:
                queued = await dequeue_training_job(timeout_seconds=interval)
                if queued:
                    await self.process_job(queued)
                    continue
                client = self._get_client()
                result = client.table("training_jobs").select("id").eq("status", "queued").order("created_at").limit(1).execute()
                if result.data:
                    await self.process_job(result.data[0]["id"])
                else:
                    await asyncio.sleep(interval)
            except Exception as exc:
                logger.error("training_worker_error error=%s", str(exc))
                await asyncio.sleep(interval)

    def stop(self) -> None:
        self._running = False
        logger.info("training_worker_stopped")


def create_training_worker() -> TrainingWorker:
    """Create a training worker instance."""
    return TrainingWorker()
