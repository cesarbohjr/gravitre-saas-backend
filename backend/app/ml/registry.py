"""Model registry for versioning and deployment."""
from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import re
from urllib.parse import urlparse
from typing import Any
from uuid import uuid4

import httpx

from app.config import get_settings
from app.core.io_pool import run_io
from app.core.logging import get_logger
from app.ml.base import ModelMetrics, ModelStatus, ModelType, ModelVersion, TrainedModel
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


def _resolve_created_by(client, user_id: str | None) -> str | None:
    """Only persist created_by when the user row exists (avoids FK 500s)."""
    if not user_id:
        return None
    try:
        result = client.table("users").select("id").eq("id", user_id).limit(1).execute()
        if result.data:
            return user_id
    except Exception as exc:
        logger.warning("created_by_lookup_failed user_id=%s error=%s", user_id, exc)
    return None


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
        payload: dict[str, Any] = {
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
            "created_at": model.created_at.isoformat(),
            "updated_at": model.updated_at.isoformat(),
        }
        created_by_safe = _resolve_created_by(client, created_by)
        if created_by_safe:
            payload["created_by"] = created_by_safe
        try:
            client.table("trained_models").insert(payload).execute()
        except Exception as exc:
            logger.error("model_insert_failed org_id=%s name=%s error=%s", org_id, name, exc)
            raise ValueError(f"Database could not save the model registry entry: {exc}") from exc
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
        # Keep manual API deployment and automatic promotion on the same gates.
        # Catalog status is implementation metadata, never deployment evidence.
        from app.ml.automatic_training import CONSENT_MANAGED_MODELS
        from app.ml.intelligence_training import CATALOG_MODEL_NAMES, champion_challenger_decision
        from app.ml.training_consent import training_is_approved

        catalog_name = next((key for key, name in CATALOG_MODEL_NAMES.items()
                             if name == model_data.get("name")), model_data.get("base_model"))
        deploy_version = version if version is not None else model_data["current_version"]
        if type(deploy_version) is not int or deploy_version < 1:
            raise ValueError("A positive artifact version is required")
        if catalog_name in CONSENT_MANAGED_MODELS:
            org_id = model_data.get("org_id")
            if not org_id or not await training_is_approved(org_id, catalog_name, self.settings):
                raise ValueError("training_consent_required")
            challenger = await self.get_version_metrics(model_id, deploy_version)
            champion_version = model_data.get("deployed_version")
            from app.core.safe_dict import safe_normalize_stored_dict
            from app.ml.federated_adoption import ALGORITHM
            custom = safe_normalize_stored_dict(safe_normalize_stored_dict(challenger).get("custom_metrics"))
            if custom.get("algorithm") == ALGORITHM:
                if (custom.get("compared_champion_model") != model_id
                        or custom.get("compared_champion_version") != champion_version):
                    raise ValueError("federated_source_champion_changed")
                if not await training_is_approved(org_id,"federated_learning",self.settings):
                    raise ValueError("federated_consent_required")
            champion = (await self.get_version_metrics(model_id, champion_version)
                        if champion_version is not None else None)
            permitted, reason, _ = champion_challenger_decision(
                challenger, champion, has_champion=champion_version is not None,
            )
            if not permitted:
                raise ValueError(reason)
        version_result = client.table("model_versions").select("id,artifact_url").eq("model_id", model_id).eq("version", deploy_version).execute()
        if not version_result.data:
            raise ValueError(f"Version {deploy_version} not found for model {model_id}")
        if catalog_name in CONSENT_MANAGED_MODELS and not version_result.data[0].get("artifact_url"):
            raise ValueError("catalog_artifact_required")
        if catalog_name == "retrieval_ranker" and custom.get("algorithm") == ALGORITHM:
            from app.ml.learning_to_rank import RetrievalRanker
            from app.ml.federated_adoption import artifact_permission
            loaded = RetrievalRanker()
            loaded.load(await self.load_model_artifact(model_id,deploy_version))
            if (loaded.federation != {"round_id":custom.get("federated_round"),"audit_digest":custom.get("federated_audit_digest")}
                    or not await artifact_permission(org_id,loaded,self.settings)):
                raise ValueError("federated_artifact_permission_or_provenance_required")
        query = client.table("trained_models").update(
            {
                "deployed_version": deploy_version,
                "status": ModelStatus.DEPLOYED.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", model_id).eq("org_id",model_data["org_id"])
        previous_version = model_data.get("deployed_version")
        query = query.is_("deployed_version","null") if previous_version is None else query.eq("deployed_version",previous_version)
        if not query.execute().data:
            return False
        logger.info("model_deployed model_id=%s version=%s", model_id, deploy_version)
        return True

    async def get_version_metrics(self, model_id: str, version: int) -> dict[str, Any] | None:
        """Return the stored ``model_versions.metrics`` for one version, or None."""
        client = self._get_client()
        result = await run_io(
            client.table("model_versions")
            .select("metrics")
            .eq("model_id", model_id)
            .eq("version", version)
            .limit(1)
            .execute
        )
        rows = result.data or []
        if not rows:
            return None
        metrics = rows[0].get("metrics")
        return metrics if isinstance(metrics, dict) else None

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
        def _select() -> Any:
            query = self._get_client().table("trained_models").select("*").eq("org_id", org_id)
            if model_type:
                query = query.eq("model_type", model_type.value)
            if status:
                query = query.eq("status", status.value)
            return query.order("updated_at", desc=True).execute()

        # Runs on every assistant turn (task classifier), so the read stays off
        # the event loop.
        result = await run_io(_select)
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
        client = await run_io(self._get_client)
        result = await run_io(
            client.table("trained_models").select("deployed_version, current_version").eq("id", model_id).execute
        )
        if not result.data:
            raise ValueError(f"Model {model_id} not found")
        model_data = result.data[0]
        load_version = version or model_data["deployed_version"] or model_data["current_version"]
        version_result = await run_io(
            client.table("model_versions").select("artifact_url").eq("model_id", model_id).eq("version", load_version).execute
        )
        if not version_result.data:
            raise ValueError(f"Version {load_version} not found")
        artifact_url = version_result.data[0]["artifact_url"]
        return await self._download_artifact(artifact_url,model_id=model_id,version=load_version)

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
        query = client.table("model_predictions").insert(
            {
                "org_id": org_id,
                "model_id": model_id,
                "version": version,
                "input_hash": input_hash,
                "prediction": prediction,
                "latency_ms": int(latency_ms),
            }
        )
        await run_io(query.execute)

    async def _upload_artifact(self, model_id: str, version: int, data: bytes) -> str:
        """Upload via current Vercel Blob put API (pathname query + access header)."""
        blob_token = self.settings.blob_read_write_token
        if not blob_token:
            raise ValueError("BLOB_READ_WRITE_TOKEN not configured")
        # Store is private-access; downloads must send the same Bearer token.
        filename = f"models/{model_id}/v{version}.pkl"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.put(
                "https://blob.vercel-storage.com/",
                params={"pathname": filename},
                content=data,
                headers={
                    "Authorization": f"Bearer {blob_token}",
                    "x-api-version": "12",
                    "x-content-type": "application/octet-stream",
                    "x-vercel-blob-access": "private",
                    "x-add-random-suffix": "0",
                    "x-allow-overwrite": "1",
                },
            )
            if response.status_code >= 400:
                logger.error(
                    "blob_upload_failed status=%s pathname=%s body=%s",
                    response.status_code,
                    filename,
                    (response.text or "")[:500],
                )
            response.raise_for_status()
            result = response.json()
        self._validate_artifact_url(result["url"],model_id,version)
        return result["url"]

    def _validate_artifact_url(self,url: str,model_id: str,version: int) -> None:
        # Same store-id normalization as Vercel's resolveBlobAuth helper.
        # A tenant-editable registry URL must not receive the global Blob key
        # or point at another model's private artifact in the same store.
        blob_token = self.settings.blob_read_write_token
        parts = blob_token.split('_') if isinstance(blob_token,str) else []
        store = parts[3] if len(parts) >= 4 and parts[:3] == ['vercel','blob','rw'] else ''
        configured = getattr(self.settings,'blob_store_id','')
        if configured:
            configured = configured.removeprefix('store_')
        parsed = urlparse(url)
        if (not re.fullmatch(r'[A-Za-z0-9-]+',store)
                or configured and configured.lower() != store.lower()
                or not isinstance(model_id,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,80}',model_id)
                or type(version) is not int or version < 1
                or parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in {None,443}
                or parsed.hostname != store.lower()+'.private.blob.vercel-storage.com'
                or parsed.path != f'/models/{model_id}/v{version}.pkl' or parsed.query or parsed.fragment):
            raise ValueError('Artifact must belong to the configured private store and requested model/version')

    async def _download_artifact(self, url: str, *, model_id: str, version: int) -> bytes:
        self._validate_artifact_url(url,model_id,version)
        limit = 128*1024*1024
        async with asyncio.timeout(60):
            async with httpx.AsyncClient(timeout=60.0,follow_redirects=False) as client:
                async with client.stream('GET',url,headers={'Authorization':f'Bearer {self.settings.blob_read_write_token}'}) as response:
                    response.raise_for_status()
                    if response.status_code != 200:
                        raise ValueError('Artifact redirect or incomplete response refused')
                    if int(response.headers.get('content-length','0')) > limit:
                        raise ValueError('Artifact exceeds bounded model size')
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > limit:
                            raise ValueError('Artifact exceeds bounded model size')
        if not content:
            raise ValueError('Empty model artifact')
        return bytes(content)


_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    """Get model registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
