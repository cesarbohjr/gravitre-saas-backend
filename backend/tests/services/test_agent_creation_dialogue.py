"""Agent/workflow creation should use conversational dialogue, not execution."""
from __future__ import annotations

import pytest

from app.services.clarification_engine import ClarificationEngine
from app.services.contextual_understanding_service import ContextualUnderstandingService
from app.services.task_classifier import TaskClassifier


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
    engine._state.get_task_state = pytest.importorskip("unittest.mock").AsyncMock(
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
