from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ml.base import ModelMetrics, ModelType
from app.ml.inference import InferenceService
from app.ml.registry import ModelRegistry


@pytest.mark.asyncio
async def test_registry_create_add_version_and_list(monkeypatch):
    registry = ModelRegistry()
    fake_client = MagicMock()

    table = MagicMock()
    fake_client.table.return_value = table
    table.insert.return_value.execute.return_value = SimpleNamespace(data=[{"id": "ok"}])
    table.update.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[{"id": "ok"}])
    table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[{"id": "m1", "current_version": 0}])

    monkeypatch.setattr("app.ml.registry.get_supabase_client", lambda settings: fake_client)
    monkeypatch.setattr(registry, "_upload_artifact", AsyncMock(return_value="https://blob.test/model.pkl"))

    model = await registry.create_model("org1", "risk-model", ModelType.CLASSIFIER)
    assert model.name == "risk-model"

    version = await registry.add_version("m1", b"blob", ModelMetrics(accuracy=0.9))
    assert version.version == 1


@pytest.mark.asyncio
async def test_inference_predict_with_stubbed_runtime(monkeypatch):
    service = InferenceService()

    fake_registry = MagicMock()
    fake_registry.get_model = AsyncMock(
        return_value=SimpleNamespace(
            id="m1",
            org_id="org1",
            model_type=ModelType.CLASSIFIER,
            deployed_version=1,
            current_version=1,
        )
    )
    fake_registry.log_prediction = AsyncMock(return_value=None)
    monkeypatch.setattr("app.ml.inference.get_model_registry", lambda: fake_registry)

    runtime = MagicMock()
    runtime.predict = AsyncMock(return_value=(["safe"], [{"safe": 0.9, "risk": 0.1}]))
    monkeypatch.setattr(service, "_load_runtime_model", AsyncMock(return_value=runtime))

    result = await service.predict("org1", "m1", [{"a": 1}], return_probabilities=True)
    assert result.model_id == "m1"
    assert result.predictions == ["safe"]
