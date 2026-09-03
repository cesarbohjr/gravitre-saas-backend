"""Tests for Agent Identity IAM service and write-gate integration."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.agent_identity_service import (
    AGENT_SPEND_LIMIT_EXCEEDED,
    AgentSpendLimitExceededError,
    EffectiveAgentIdentity,
    enforce_agent_identity_before_tool,
    resolve_effective_identity,
    tool_matches_patterns,
    upsert_agent_identity_record,
)
from app.services.react_write_gate import block_react_write_execution


def test_tool_matches_patterns_hubspot_wildcard():
    assert tool_matches_patterns(
        "hubspot_contacts_create",
        "hubspot.contacts.create",
        ("hubspot.*",),
    )


def test_enforce_blocks_read_only_write():
    client = MagicMock()
    agent_id = "00000000-0000-4000-8000-000000000001"
    identity = EffectiveAgentIdentity(
        org_id="org-1",
        agent_id=agent_id,
        trust_level="read_only",
        allowed_tool_patterns=(),
        allowed_action_kinds=frozenset({"read", "write"}),
        allowed_data_scopes=(),
        max_actions_per_day=None,
        max_tokens_per_day=None,
        max_spend_usd_per_day=None,
        can_delegate=False,
        approval_rule_overrides={},
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.agent_identity_service.resolve_effective_identity",
            lambda *_a, **_k: identity,
        )
        mp.setattr("app.services.agent_identity_service.write_audit_event", lambda *_a, **_k: None)
        from app.services.agent_identity_service import AgentIdentityDeniedError

        with pytest.raises(AgentIdentityDeniedError) as exc:
            enforce_agent_identity_before_tool(
                client,
                "org-1",
                agent_id,
                tool_name="hubspot_contacts_create",
                invoke_action="hubspot.contacts.create",
                action_kind="write",
            )
        assert exc.value.reason == "read_only"


def test_spend_limit_raises_when_over_cap():
    client = MagicMock()
    identity = EffectiveAgentIdentity(
        org_id="org-1",
        agent_id="agent-1",
        trust_level="write_with_approval",
        allowed_tool_patterns=(),
        allowed_action_kinds=frozenset({"read", "write"}),
        allowed_data_scopes=(),
        max_actions_per_day=None,
        max_tokens_per_day=None,
        max_spend_usd_per_day=0.01,
        can_delegate=False,
        approval_rule_overrides={},
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.agent_identity_service.resolve_effective_identity",
            lambda *_a, **_k: identity,
        )
        mp.setattr(
            "app.services.agent_identity_service.get_daily_usage",
            lambda *_a, **_k: {"actions": 0.0, "tokens": 0.0, "spendUsd": 0.01},
        )
        mp.setattr("app.services.agent_identity_service.write_audit_event", lambda *_a, **_k: None)
        with pytest.raises(AgentSpendLimitExceededError):
            enforce_agent_identity_before_tool(
                client,
                "org-1",
                "00000000-0000-4000-8000-000000000001",
                tool_name="hubspot_contacts_create",
                invoke_action="hubspot.contacts.create",
                action_kind="write",
            )


def test_block_react_write_execution_returns_spend_error_code():
    client = MagicMock()
    registry = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.react_write_gate.tool_requires_user_write_approval",
            lambda *_a, **_k: (True, "hubspot.contacts.create", "hubspot", "Create contact"),
        )
        mp.setattr(
            "app.services.agent_identity_service.enforce_agent_identity_before_tool",
            lambda *_a, **_k: (_ for _ in ()).throw(
                AgentSpendLimitExceededError(
                    dimension="spend_usd",
                    limit=0.01,
                    used=0.01,
                    agent_id="00000000-0000-4000-8000-000000000001",
                )
            ),
        )
        blocked = block_react_write_execution(
            "hubspot_contacts_create",
            {"email": "x@example.com"},
            registry,
            client=client,
            org_id="org-1",
            user_id="user-1",
            agent_id="00000000-0000-4000-8000-000000000001",
        )
    assert blocked is not None
    assert blocked.get("error_code") == AGENT_SPEND_LIMIT_EXCEEDED
