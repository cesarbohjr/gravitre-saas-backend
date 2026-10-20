"""Deployment metadata must never substitute for a successful artifact load."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.ml.model_catalog import get_org_model_status


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "download", "deserialize"])
async def test_catalog_verifies_deployed_artifact(failure):
    registry = Mock()
    registry.list_models = AsyncMock(return_value=[SimpleNamespace(
        id="model-1", name="catalog-churn-risk", deployed_version=2,
    )])
    registry.load_model_artifact = AsyncMock(return_value=b"artifact")
    runtime = Mock()
    if failure == "download":
        registry.load_model_artifact.side_effect = RuntimeError("unavailable")
    if failure == "deserialize":
        runtime.load.side_effect = ValueError("incompatible artifact")
    with (
        patch("app.ml.model_catalog._count_org_data_points", return_value={}),
        patch("app.ml.model_catalog.get_model_instance", return_value=runtime),
        patch("app.ml.registry.get_model_registry", return_value=registry),
    ):
        result = await get_org_model_status("org-1", "churn_risk_scorer", settings=Mock())
    registry.list_models.assert_awaited_once_with(org_id="org-1")
    registry.load_model_artifact.assert_awaited_once_with("model-1", 2)
    assert result["deployed_version"] == 2
    assert result["artifact_loaded"] is (failure is None)
    assert result["runtime_status"] == ("trained" if failure is None else "heuristic")
    if failure:
        assert result["artifact_load_failed"] is True
    else:
        runtime.load.assert_called_once_with(b"artifact")
