"""P0: conversational model routing must be intentional across text and voice."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.unified_turn_reasoning_service import _resolve_model


def _settings(**overrides):
    base = {
        "voice_conversational_model": "",
        "unified_turn_task_model_tier": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_conversational_depth_uses_quality_tier_when_voice_override_is_unset() -> None:
    assert _resolve_model(_settings(), reasoning_depth="conversational") == "gpt-6.1-sol"


def test_voice_fast_model_requires_explicit_configuration() -> None:
    assert (
        _resolve_model(
            _settings(voice_conversational_model="gpt-5.4-mini"),
            reasoning_depth="conversational",
        )
        == "gpt-5.4-mini"
    )


def test_unified_full_depth_does_not_fall_through_to_legacy_gpt4o_mini() -> None:
    assert _resolve_model(_settings(), reasoning_depth="full", task_shaped=False) == "gpt-6.1-sol"


def test_task_tier_is_honored_when_explicitly_configured() -> None:
    assert (
        _resolve_model(
            _settings(unified_turn_task_model_tier="low"),
            reasoning_depth="full",
            task_shaped=True,
        )
        == "gpt-6-luna"
    )
