"""Wave 4 — complexity classifier for assistant model routing."""
from __future__ import annotations

from app.services.assistant_turn_complexity import (
    classify_assistant_turn_complexity,
    model_tier_for_task_type,
)
from app.services.model_router import TaskType


def test_fast_short_message_is_low_tier():
    task = classify_assistant_turn_complexity("What is Gravitre?", mode="fast")
    assert task == TaskType.SUMMARIZATION
    assert model_tier_for_task_type(task) == "low"


def test_connector_create_is_workflow_planning():
    task = classify_assistant_turn_complexity(
        "create MSP Prospects list in Apollo",
        mode="standard",
        connected_integrations=["apollo"],
    )
    assert task == TaskType.WORKFLOW_PLANNING
    assert model_tier_for_task_type(task) == "high"


def test_multi_step_hint_is_workflow_planning():
    task = classify_assistant_turn_complexity(
        "Search HubSpot then create a deal after that",
        mode="standard",
    )
    assert task == TaskType.WORKFLOW_PLANNING


def test_default_is_rag_answering():
    task = classify_assistant_turn_complexity(
        "Summarize our Q2 pipeline health for the team",
        mode="standard",
    )
    assert task == TaskType.RAG_ANSWERING
    assert model_tier_for_task_type(task) == "medium"


def test_explicit_high_complexity_param():
    task = classify_assistant_turn_complexity(
        "hi",
        mode="fast",
        parameters={"complexity": "high"},
    )
    assert task == TaskType.DECISION_REASONING
