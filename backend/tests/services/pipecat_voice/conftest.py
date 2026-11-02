"""Explicit external-source fixtures for scripted voice pipeline unit tests."""
from unittest.mock import AsyncMock

import pytest

from tests.services.fake_supabase_db import FakeSupabaseDB


@pytest.fixture
def scripted_voice_external_sources(monkeypatch):
    """Keep real guardrail code; replace its external policy/budget/moderation data.

    Only modules explicitly marked with usefixtures opt in. Real guardrail,
    refusal, billing, model-policy and provider tests do not inherit this fixture.
    No production flag, guard function or test assertion is bypassed.
    """
    from app.services.ai_guardrails import clear_moderation_cache

    clear_moderation_cache()
    db = FakeSupabaseDB()
    monkeypatch.setattr("app.services.model_router.get_supabase_client", lambda *_: db)
    monkeypatch.setattr("app.billing.service.get_supabase_client", lambda *_: db)
    moderation = AsyncMock(return_value=False)
    monkeypatch.setattr("app.services.ai_guardrails._moderation_flagged", moderation)
    yield db, moderation
    # Synthetic passes must not escape this fixture into other policy tests.
    clear_moderation_cache()
