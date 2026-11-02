"""Fixture regression: real model-policy and moderation refusals still work."""
from types import SimpleNamespace

import pytest

from app.services.ai_guardrails import AIContentFlaggedError, AIModelPolicyError, clear_moderation_cache, moderate_input
from app.services.model_router import ModelRouter

# Scripted brain events; provider policy/budget data is supplied by an explicit offline fixture.
pytestmark = pytest.mark.usefixtures("scripted_voice_external_sources")

pytestmark = pytest.mark.usefixtures("scripted_voice_external_sources")


def test_scripted_fixture_does_not_bypass_real_model_policy(scripted_voice_external_sources):
    db, _ = scripted_voice_external_sources
    db.tables["organizations"] = [{"id": "tenant-a", "settings": {"modelPolicy": {
        "mode": "blocklist", "models": ["gpt-4o"], "providers": []}}}]
    router = object.__new__(ModelRouter)
    router.settings = SimpleNamespace()
    with pytest.raises(AIModelPolicyError):
        router._assert_model_policy("tenant-a", "gpt-4o")


@pytest.mark.asyncio
async def test_scripted_fixture_keeps_real_moderation_refusal(scripted_voice_external_sources):
    _, provider_response = scripted_voice_external_sources
    clear_moderation_cache()
    provider_response.return_value = True
    with pytest.raises(AIContentFlaggedError):
        await moderate_input("synthetic flagged text", SimpleNamespace(ai_moderation_enabled=True), object())
    provider_response.assert_awaited_once()
