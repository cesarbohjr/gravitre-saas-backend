"""Unit tests for conversational-depth unified-turn model selection."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.unified_turn_reasoning_service import (
    _resolve_model,
    _resolve_unified_turn_model,
)


def test_conversational_depth_forces_gpt_4o_mini_even_when_task_shaped():
    settings = SimpleNamespace(unified_turn_task_model_tier="low")
    assert _resolve_model(settings, task_shaped=True, reasoning_depth="conversational") == "gpt-4o-mini"
    assert (
        _resolve_unified_turn_model(
            settings,
            agent={"model": "gpt-5.4-mini"},
            task_shaped=True,
            reasoning_depth="conversational",
        )
        == "gpt-4o-mini"
    )


def test_full_depth_keeps_task_tier_and_agent_pin(monkeypatch):
    from app.config import MODEL_TIERS

    settings = SimpleNamespace(unified_turn_task_model_tier="low")
    low = (MODEL_TIERS.get("low") or {}).get("openai") or "gpt-5.4-mini"
    assert _resolve_model(settings, task_shaped=True, reasoning_depth="full") == low
    assert (
        _resolve_unified_turn_model(
            settings,
            agent={"model": "gpt-4o"},
            task_shaped=True,
            reasoning_depth="full",
        )
        == "gpt-4o"
    )
