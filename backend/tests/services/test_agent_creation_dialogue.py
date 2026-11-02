"""Agent/workflow creation should use conversational dialogue, not execution."""
from __future__ import annotations

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.clarification_engine import ClarificationEngine
from app.services.contextual_understanding_service import ContextualUnderstandingService
from app.services.task_classifier import TaskClassifier


@pytest.fixture(autouse=True)
def offline_optional_model_boundary(monkeypatch):
    # These tests exercise native planning and clarification templates, not a
    # provider. The previous implicit failure/fallback attempted real egress
    # using fixture credentials. Keep all behavioral assertions unchanged and
    # make the optional empty model response explicit before the router runs.
    from tests.support.fake_supabase import FakeSupabase

    db = FakeSupabase()
    db.tables["organizations"] = [{"id": "org-1", "settings": {}}]
    monkeypatch.setattr("app.services.domain_intelligence_service.get_supabase_client", lambda *_: db)
    monkeypatch.setattr("app.ml.training_consent.get_supabase_client", lambda *_: db)
    monkeypatch.setattr(
        "app.services.model_router.get_model_router",
        lambda: SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(content=""))),
    )


@pytest.mark.asyncio
async def test_create_agent_is_conversational_planning():
    understanding = await ContextualUnderstandingService().understand(
        "create an agent",
        [],
        "org-1",
    )
    assert understanding["conversational_create"] is True
    assert understanding["expected_output_format"] == "plan"

    classification = await TaskClassifier().classify(
        "org-1",
        "create an agent",
        understanding=understanding,
    )
    assert classification["intent"] == "workflow_planning"
    assert classification["requires_action"] is False


@pytest.mark.asyncio
async def test_create_agent_triggers_name_and_purpose_clarification():
    engine = ClarificationEngine()
    engine._state.get_task_state = AsyncMock(
        return_value={"clarified_params": {}},
    )

    understanding = {"conversational_create": True}
    classification = {
        "request": "create an agent",
        "classification_confidence": 0.8,
        "requires_action": False,
        "intent": "workflow_planning",
    }

    result = await engine.should_clarify(
        classification,
        {},
        [],
        understanding=understanding,
    )
    assert result["should_clarify"] is True
    assert "call it" in result["question"].lower() or "name" in result["question"].lower()
