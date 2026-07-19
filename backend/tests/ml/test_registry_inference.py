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


@pytest.mark.asyncio
async def test_upload_artifact_uses_vercel_blob_put_api(monkeypatch):
    registry = ModelRegistry()
    registry._settings = SimpleNamespace(blob_read_write_token="vercel_blob_rw_test")

    captured: dict = {}

    class _Resp:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {"url": "https://example.public.blob.vercel-storage.com/models/m1/v1.pkl"}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def put(self, url, params=None, content=None, headers=None):
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            captured["content"] = content
            return _Resp()

    monkeypatch.setattr("app.ml.registry.httpx.AsyncClient", _Client)

    url = await registry._upload_artifact("m1", 1, b"pickle-bytes")
    assert url.endswith("/models/m1/v1.pkl")
    assert captured["url"] == "https://blob.vercel-storage.com/"
    assert captured["params"] == {"pathname": "models/m1/v1.pkl"}
    assert captured["headers"]["Authorization"] == "Bearer vercel_blob_rw_test"
    assert captured["headers"]["x-api-version"] == "12"
    assert captured["headers"]["x-vercel-blob-access"] == "public"
    assert captured["content"] == b"pickle-bytes"
