"""Model registry for versioning and deployment."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx

from app.config import get_settings
from app.core.logging import get_logger
from app.ml.base import ModelMetrics, ModelStatus, ModelType, ModelVersion, TrainedModel
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class ModelRegistry:
    """Manages model storage, versioning, and deployment."""

    def __init__(self):
        self._settings = None

    @property
    def settings(self):
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_client(self):
        return get_supabase_client(self.settings)

    async def create_model(
        self,
        org_id: str,
        name: str,
        model_type: ModelType,
        description: str | None = None,
        dataset_id: str | None = None,
        base_model: str | None = None,
        task_type: str | None = None,
        created_by: str | None = None,
    ) -> TrainedModel:
        client = self._get_client()
        model = TrainedModel(
            id=str(uuid4()),
            org_id=org_id,
            name=name,
            description=description,
            model_type=model_type,
            status=ModelStatus.DRAFT,
            dataset_id=dataset_id,
            base_model=base_model,
            task_type=task_type,
            created_by=created_by,
        )
        client.table("trained_models").insert(
            {
                "id": model.id,
                "org_id": org_id,
                "name": name,
                "description": description,
                "model_type": model_type.value,
                "status": model.status.value,
                "current_version": 0,
                "deployed_version": None,
                "dataset_id": dataset_id,
                "base_model": base_model,
                "task_type": task_type,
                "created_by": created_by,
                "created_at": model.created_at.isoformat(),
                "updated_at": model.updated_at.isoformat(),
            }
        ).execute()
        logger.info("model_created model_id=%s name=%s type=%s", model.id, name, model_type.value)
        return model

    async def add_version(
        self,
        model_id: str,
        artifact_data: bytes,
        metrics: ModelMetrics,
        hyperparameters: dict[str, Any] | None = None,
        feature_names: list[str] | None = None,
        label_encoder: dict[str, int] | None = None,
        created_by: str | None = None,
    ) -> ModelVersion:
        client = self._get_client()
        result = client.table("trained_models").select("*").eq("id", model_id).execute()
        if not result.data:
            raise ValueError(f"Model {model_id} not found")
        model_data = result.data[0]
        new_version = int(model_data["current_version"]) + 1
        artifact_url = await self._upload_artifact(model_id, new_version, artifact_data)
        version = ModelVersion(
            id=str(uuid4()),
            model_id=model_id,
            version=new_version,
            artifact_url=artifact_url,
            artifact_size_bytes=len(artifact_data),
            metrics=metrics,
            hyperparameters=hyperparameters or {},
            feature_names=feature_names or [],
            label_encoder=label_encoder,
            created_by=created_by,
        )
        client.table("model_versions").insert(
            {
                "id": version.id,
                "model_id": model_id,
                "version": new_version,
                "artifact_url": artifact_url,
                "artifact_size_bytes": len(artifact_data),
                "metrics": metrics.model_dump(),
                "hyperparameters": version.hyperparameters,
                "feature_names": version.feature_names,
                "label_encoder": version.label_encoder,
                "created_at": version.created_at.isoformat(),
                "created_by": created_by,
            }
        ).execute()
        client.table("trained_models").update(
            {
                "current_version": new_version,
                "status": ModelStatus.READY.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", model_id).execute()
        logger.info("model_version_added model_id=%s version=%s", model_id, new_version)
        return version

    async def deploy_version(self, model_id: str, version: int | None = None) -> bool:
        client = self._get_client()
        result = client.table("trained_models").select("*").eq("id", model_id).execute()
        if not result.data:
            raise ValueError(f"Model {model_id} not found")
        model_data = result.data[0]
        deploy_version = version or model_data["current_version"]
        version_result = client.table("model_versions").select("id").eq("model_id", model_id).eq("version", deploy_version).execute()
        if not version_result.data:
            raise ValueError(f"Version {deploy_version} not found for model {model_id}")
        client.table("trained_models").update(
            {
                "deployed_version": deploy_version,
                "status": ModelStatus.DEPLOYED.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", model_id).execute()
        logger.info("model_deployed model_id=%s version=%s", model_id, deploy_version)
        return True

    async def get_model(self, model_id: str) -> TrainedModel | None:
        client = self._get_client()
        result = client.table("trained_models").select("*").eq("id", model_id).execute()
        if not result.data:
            return None
        data = result.data[0]
        versions_result = client.table("model_versions").select("*").eq("model_id", model_id).order("version", desc=True).execute()
        versions = [
            ModelVersion(
                id=v["id"],
                model_id=v["model_id"],
                version=v["version"],
                artifact_url=v["artifact_url"],
                artifact_size_bytes=v["artifact_size_bytes"],
                metrics=ModelMetrics(**v["metrics"]),
                hyperparameters=v["hyperparameters"],
                feature_names=v["feature_names"],
                label_encoder=v["label_encoder"],
                created_at=datetime.fromisoformat(v["created_at"].replace("Z", "+00:00")),
                created_by=v["created_by"],
            )
            for v in (versions_result.data or [])
        ]
        return TrainedModel(
            id=data["id"],
            org_id=data["org_id"],
            name=data["name"],
            description=data["description"],
            model_type=ModelType(data["model_type"]),
            status=ModelStatus(data["status"]),
            current_version=data["current_version"],
            deployed_version=data["deployed_version"],
            dataset_id=data["dataset_id"],
            base_model=data["base_model"],
            task_type=data["task_type"],
            feature_columns=data.get("feature_columns", []),
            versions=versions,
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            created_by=data["created_by"],
        )

    async def list_models(
        self,
        org_id: str,
        model_type: ModelType | None = None,
        status: ModelStatus | None = None,
    ) -> list[TrainedModel]:
        client = self._get_client()
        query = client.table("trained_models").select("*").eq("org_id", org_id)
        if model_type:
            query = query.eq("model_type", model_type.value)
        if status:
            query = query.eq("status", status.value)
        result = query.order("updated_at", desc=True).execute()
        models: list[TrainedModel] = []
        for data in (result.data or []):
            models.append(
                TrainedModel(
                    id=data["id"],
                    org_id=data["org_id"],
                    name=data["name"],
                    description=data["description"],
                    model_type=ModelType(data["model_type"]),
                    status=ModelStatus(data["status"]),
                    current_version=data["current_version"],
                    deployed_version=data["deployed_version"],
                    dataset_id=data["dataset_id"],
                    base_model=data["base_model"],
                    task_type=data["task_type"],
                    created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
                    created_by=data["created_by"],
                )
            )
        return models

    async def load_model_artifact(self, model_id: str, version: int | None = None) -> bytes:
        client = self._get_client()
        result = client.table("trained_models").select("deployed_version, current_version").eq("id", model_id).execute()
        if not result.data:
            raise ValueError(f"Model {model_id} not found")
        model_data = result.data[0]
        load_version = version or model_data["deployed_version"] or model_data["current_version"]
        version_result = client.table("model_versions").select("artifact_url").eq("model_id", model_id).eq("version", load_version).execute()
        if not version_result.data:
            raise ValueError(f"Version {load_version} not found")
        artifact_url = version_result.data[0]["artifact_url"]
        return await self._download_artifact(artifact_url)

    async def log_prediction(
        self,
        org_id: str,
        model_id: str,
        version: int,
        input_hash: str,
        prediction: dict[str, Any],
        latency_ms: float,
    ) -> None:
        client = self._get_client()
        client.table("model_predictions").insert(
            {
                "org_id": org_id,
                "model_id": model_id,
                "version": version,
                "input_hash": input_hash,
                "prediction": prediction,
                "latency_ms": int(latency_ms),
            }
        ).execute()

    async def _upload_artifact(self, model_id: str, version: int, data: bytes) -> str:
        blob_token = self.settings.blob_read_write_token
        if not blob_token:
            raise ValueError("BLOB_READ_WRITE_TOKEN not configured")
        filename = f"models/{model_id}/v{version}.pkl"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.put(
                f"https://blob.vercel-storage.com/{filename}",
                content=data,
                headers={
                    "Authorization": f"Bearer {blob_token}",
                    "x-content-type": "application/octet-stream",
                },
            )
            response.raise_for_status()
            result = response.json()
        return result["url"]

    async def _download_artifact(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        return response.content


_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    """Get model registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
