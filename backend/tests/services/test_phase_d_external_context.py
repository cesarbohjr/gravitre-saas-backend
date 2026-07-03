"""Phase D: external context and multimodal ingest."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.rag.file_extract import _IMAGE_EXTENSIONS, supported_upload_extensions
from app.services.assistant_availability import is_external_or_general_question
from app.services.learning_strategy_keys import build_route_strategy_key
from app.services.research_service import AutonomousResearchService
from app.services.task_classifier import TaskClassifier


def test_learning_strategy_key_includes_web_dimension():
    key = build_route_strategy_key({}, {"intent": "question_answering"}, {"web": True})
    assert key.endswith(":web")


def test_supported_upload_extensions_include_images():
    assert ".png" in supported_upload_extensions()
    assert _IMAGE_EXTENSIONS


@pytest.mark.asyncio
async def test_task_classifier_sets_web_search_for_external_questions():
    classifier = TaskClassifier()
    with patch.object(classifier, "_classify_with_ml", AsyncMock(return_value={"intent": "question_answering", "classification_confidence": 0.6})):
        with patch(
            "app.services.assistant_availability.is_web_search_configured",
            return_value=True,
        ):
            result = await classifier.classify("org-1", "What is the latest market trend in AI?")
    assert result.get("requires_web_search") is True


@pytest.mark.asyncio
async def test_research_includes_web_when_external_topic():
    service = AutonomousResearchService()
    with patch(
        "app.services.research_service.get_rag_service"
    ) as rag_factory:
        rag_factory.return_value.query = AsyncMock(return_value=type("R", (), {"chunks": []})())
        with patch(
            "app.services.assistant_availability.is_web_search_configured",
            return_value=True,
        ):
            with patch(
                "app.services.web_research.search_web",
                AsyncMock(return_value={"results": [{"url": "https://a.test", "snippet": "Trend", "title": "T"}]}),
            ):
                with patch(
                    "app.services.external_knowledge_service.gather_external_knowledge",
                    AsyncMock(return_value=[]),
                ):
                    with patch.object(service, "score_source_credibility", AsyncMock(return_value=0.6)):
                        result = await service.research("org-1", "What is quantum computing?", depth="standard")
    assert any(f.get("type") == "web" for f in result.get("findings") or [])


def test_external_question_heuristic():
    assert is_external_or_general_question("What is the latest news in fintech?") is True
    assert is_external_or_general_question("Show our HubSpot pipeline") is False
