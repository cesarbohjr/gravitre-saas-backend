"""Module C Phase 2 — catalog TRAINED ≠ runtime trained without an artifact."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml.base import ModelStatus
from app.ml.model_catalog import get_org_model_status


@pytest.mark.asyncio
async def test_org_status_heuristic_when_no_deployed_artifact():
    registry = MagicMock()
    registry.list_models = AsyncMock(return_value=[])
    with (
        patch("app.ml.model_catalog._count_org_data_points", return_value={"data_counts": {}}),
        patch("app.ml.registry.get_model_registry", return_value=registry),
        patch(
            "app.ml.intelligence_training.CATALOG_MODEL_NAMES",
            {"intent_classifier": "catalog-query-intent"},
        ),
    ):
        status = await get_org_model_status("org-1", "intent_classifier")
    assert status["catalog_status"] == ModelStatus.TRAINED.value
    assert status["artifact_loaded"] is False
    assert status["runtime_status"] == "heuristic"
    assert status["live_inference_path"] != "loaded_model_artifact"


@pytest.mark.asyncio
async def test_org_status_trained_when_artifact_deployed():
    match = MagicMock()
    match.name = "catalog-query-intent"
    match.deployed_version = "v3"
    registry = MagicMock()
    registry.list_models = AsyncMock(return_value=[match])
    with (
        patch("app.ml.model_catalog._count_org_data_points", return_value={"data_counts": {}}),
        patch("app.ml.registry.get_model_registry", return_value=registry),
        patch(
            "app.ml.intelligence_training.CATALOG_MODEL_NAMES",
            {"intent_classifier": "catalog-query-intent"},
        ),
    ):
        status = await get_org_model_status("org-1", "intent_classifier")
    assert status["artifact_loaded"] is True
    assert status["runtime_status"] == "trained"
    assert status["live_inference_path"] == "loaded_model_artifact"
    assert status["deployed_version"] == "v3"
