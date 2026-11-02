"""Unit tests for conversational-depth unified-turn model selection."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from app.services.unified_turn_reasoning_service import (
    _resolve_model,
    _resolve_unified_turn_model,
)


@pytest.mark.parametrize('provider', ['openai', 'anthropic', 'gemini'])
@pytest.mark.parametrize('depth,task_shaped,tier', [
    ('conversational', False, 'low'), ('full', False, ''), ('full', True, 'low'),
    ('full', True, 'not_a_real_tier'),
])
def test_default_model_stays_in_configured_provider_family(provider, depth, task_shaped, tier):
    from app.config import MODEL_TIERS
    from app.services.providers.provider_tool_router import resolve_provider_for_model, provider_tools_configured

    settings = SimpleNamespace(preferred_ai_provider=provider,
        unified_turn_task_model_tier=tier, voice_conversational_model='',
        openai_api_key='offline' if provider == 'openai' else '',
        anthropic_api_key='offline' if provider == 'anthropic' else '',
        gemini_api_key='offline' if provider == 'gemini' else '')
    model = _resolve_unified_turn_model(settings, agent=None,
        task_shaped=task_shaped, reasoning_depth=depth)
    assert resolve_provider_for_model(model) == provider
    assert provider_tools_configured(resolve_provider_for_model(model), settings)
    expected_tier = 'low' if task_shaped and tier == 'low' and depth == 'full' else 'medium'
    assert model == MODEL_TIERS[expected_tier][provider]


def test_explicit_models_remain_explicit_with_anthropic_preference():
    settings = SimpleNamespace(preferred_ai_provider='anthropic',
        unified_turn_task_model_tier='low', voice_conversational_model='gpt-5.4-mini')
    assert _resolve_unified_turn_model(settings, agent={'model': 'gemini-2.5-pro'},
        reasoning_depth='conversational') == 'gpt-5.4-mini'
    assert _resolve_unified_turn_model(settings, agent={'model': 'gemini-2.5-pro'},
        reasoning_depth='full') == 'gemini-2.5-pro'


def test_conversational_depth_pins_voice_conversational_model():
    settings = SimpleNamespace(
        unified_turn_task_model_tier="low",
        voice_conversational_model="gpt-5.4-nano",
    )
    assert _resolve_model(settings, task_shaped=True, reasoning_depth="conversational") == "gpt-5.4-nano"
    assert (
        _resolve_unified_turn_model(
            settings,
            agent={"model": "gpt-5.4-mini"},
            task_shaped=True,
            reasoning_depth="conversational",
        )
        == "gpt-5.4-nano"
    )


def test_conversational_depth_honors_env_override():
    settings = SimpleNamespace(
        unified_turn_task_model_tier="low",
        voice_conversational_model="gpt-4o-mini",
    )
    assert _resolve_model(settings, task_shaped=True, reasoning_depth="conversational") == "gpt-4o-mini"


def test_full_depth_keeps_task_tier_and_agent_pin(monkeypatch):
    from app.config import MODEL_TIERS

    settings = SimpleNamespace(
        unified_turn_task_model_tier="low",
        voice_conversational_model="gpt-5.4-nano",
    )
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
