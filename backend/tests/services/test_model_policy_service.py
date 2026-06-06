"""STA-90: org model allowlist / blocklist policy."""
from __future__ import annotations

import pytest

from app.services.ai_guardrails import AIModelPolicyError
from app.services.model_policy_service import assert_model_allowed, normalize_model_policy


def test_open_policy_allows_all():
    assert_model_allowed({"mode": "open", "providers": [], "models": []}, provider="openai", model="gpt-5.5")


def test_allowlist_blocks_unknown_model():
    policy = normalize_model_policy({"mode": "allowlist", "providers": [], "models": ["gpt-4.1-mini"]})
    with pytest.raises(AIModelPolicyError):
        assert_model_allowed(policy, provider="openai", model="gpt-5.5")


def test_blocklist_blocks_listed_model():
    policy = normalize_model_policy({"mode": "blocklist", "providers": [], "models": ["gpt-5.5"]})
    with pytest.raises(AIModelPolicyError):
        assert_model_allowed(policy, provider="openai", model="gpt-5.5")
