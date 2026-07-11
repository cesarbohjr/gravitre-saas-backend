"""Chat intelligence facade — shared router stages for live chat."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_intelligence_facade import ChatIntelligenceFacade
from app.services.learning_strategy_keys import parse_segment_key


def test_build_route_metadata_includes_cluster_segment():
    facade = ChatIntelligenceFacade()
    classification = {
        "query_cluster_id": "cluster-1",
        "department": "sales",
        "intent": "question_answering",
    }
    meta = facade.build_route_metadata(classification, {"llm_tier": "standard"}, {})
    assert meta["segment_key"] == parse_segment_key(classification)
    assert meta["segment_key"].startswith("cluster:cluster-1:")


@pytest.mark.asyncio
async def test_resolve_chat_model_uses_model_selector():
    facade = ChatIntelligenceFacade()
    agent = {"id": "a1", "model": ""}
    classification = {"intent": "question_answering", "classification_confidence": 0.8}
    with patch(
        "app.services.chat_intelligence_facade.get_model_selector"
    ) as selector_factory:
        selector = MagicMock()
        selector.select = AsyncMock(
            return_value={"llm_tier": "fast", "primary_model": "llm", "reason": "test"}
        )
        selector_factory.return_value = selector
        with patch(
            "app.operators.agent_intelligence.resolve_agent_inference_model",
            return_value=MagicMock(fine_tuned_openai_id=None, base_model=""),
        ):
            model, meta = await facade.resolve_chat_model(
                "org-1",
                agent,
                MagicMock(),
                "hello",
                classification,
            )
    # No llm_model from selector → Wave 4 turn-complexity tier
    assert meta["source"] == "turn_complexity"
    assert meta["task_type"]
    assert model
