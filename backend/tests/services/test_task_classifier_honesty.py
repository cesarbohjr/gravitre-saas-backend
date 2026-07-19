"""Module C / STA-331 — task classifier must not fake TRAINED confidence."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.task_classifier import TaskClassifier, _intent_artifact_ready


def test_intent_artifact_ready_requires_vectorizer_and_model():
    empty = MagicMock(vectorizer=None, model=None)
    assert _intent_artifact_ready(empty) is False
    partial = MagicMock(vectorizer=object(), model=None)
    assert _intent_artifact_ready(partial) is False
    ready = MagicMock(vectorizer=object(), model=object())
    assert _intent_artifact_ready(ready) is True


@pytest.mark.asyncio
async def test_catalog_trained_without_artifact_stays_heuristic():
    classifier = TaskClassifier()
    shell = MagicMock(vectorizer=None, model=None)
    with patch(
        "app.ml.model_catalog.load_org_trained_catalog_model",
        new=AsyncMock(return_value=shell),
    ):
        result = await classifier._classify_with_ml("org-1", "what is our revenue?")
    assert result["live_inference_path"] == "heuristic"
    assert result["artifact_loaded"] is False
    assert result["confidence_is_estimate"] is True
    assert result["classification_confidence"] == 0.55
    assert result["classification_source"] == "rule_based_classify_query"


@pytest.mark.asyncio
async def test_loaded_artifact_uses_model_probability():
    classifier = TaskClassifier()
    model = MagicMock()
    model.vectorizer = object()
    model.model = object()
    model.predict_text = AsyncMock(
        return_value=(["analytics"], [{"analytics": 0.91, "general": 0.09}])
    )
    with patch(
        "app.ml.model_catalog.load_org_trained_catalog_model",
        new=AsyncMock(return_value=model),
    ):
        result = await classifier._classify_with_ml("org-1", "show pipeline analytics")
    assert result["artifact_loaded"] is True
    assert result["live_inference_path"] == "loaded_model_artifact"
    assert result["confidence_is_estimate"] is False
    assert result["classification_confidence"] == pytest.approx(0.91)
    assert result["classification_source"] == "loaded_model_artifact"
    assert result["intent"] == "data_analysis"
