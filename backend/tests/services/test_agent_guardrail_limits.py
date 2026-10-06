from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import agent_guardrail_limits as limits_mod
from app.services.agent_guardrail_limits import (
    DEFAULT_MAX_ACTIONS_PER_HOUR,
    AgentGuardrailLimitError,
    AgentLimits,
    check_agent_limits,
    enforce_agent_guardrail_limits,
    resolve_agent_limits,
)
from app.services.tool_service import invoke_tool
from app.services.tool_types import ToolContext

AGENT_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def _no_redis_and_fresh_cache():
    limits_mod.clear_agent_limits_cache()
    with patch("app.core.redis_client.get_sync_redis", return_value=None):
        yield
    limits_mod.clear_agent_limits_cache()


def test_no_rules_means_no_limits():
    assert resolve_agent_limits({"guardrails": ["Ask before making changes"]}) == AgentLimits()
    assert not resolve_agent_limits(None).active


def test_slow_down_by_name_or_id_uses_default_or_configured_number():
    assert resolve_agent_limits({"guardrails": ["Slow down"]}).max_actions_per_hour == DEFAULT_MAX_ACTIONS_PER_HOUR
    assert resolve_agent_limits({"guardrails": ["rate-limit"]}).max_actions_per_hour == DEFAULT_MAX_ACTIONS_PER_HOUR
    configured = resolve_agent_limits(
        {"guardrails": ["Slow down"], "config": {"guardrail_limits": {"max_actions_per_hour": 5}}}
    )
    assert configured.max_actions_per_hour == 5
    bad_number = resolve_agent_limits(
        {"guardrails": ["Slow down"], "config": {"guardrail_limits": {"max_actions_per_hour": "-3"}}}
    )
    assert bad_number.max_actions_per_hour == DEFAULT_MAX_ACTIONS_PER_HOUR


def test_number_without_the_rule_is_ignored():
    limits = resolve_agent_limits({"guardrails": [], "config": {"guardrail_limits": {"max_actions_per_hour": 5}}})
    assert limits.max_actions_per_hour is None


def test_workspace_limits_flag():
    assert resolve_agent_limits({"guardrails": ["Workspace limits"]}).live_read_only
    assert resolve_agent_limits({"guardrails": ["env-restrict"]}).live_read_only


def test_rate_limit_blocks_after_the_hourly_budget():
    limits = AgentLimits(max_actions_per_hour=2)
    kwargs = {"org_id": "org-1", "agent_id": "agent-rate", "action": "hubspot.contacts.search", "environment_name": "production"}
    check_agent_limits(limits, **kwargs)
    check_agent_limits(limits, **kwargs)
    with pytest.raises(AgentGuardrailLimitError) as exc:
        check_agent_limits(limits, **kwargs)
    assert exc.value.code == "AGENT_RATE_LIMITED"
    assert "2 actions per hour" in str(exc.value)
    # Another agent has its own budget.
    check_agent_limits(limits, **{**kwargs, "agent_id": "agent-other"})


@pytest.mark.parametrize(
    ("environment", "is_write", "blocked"),
    [
        ("production", True, True),
        ("default", True, True),
        ("prod", True, True),
        ("staging", True, False),
        ("production", False, False),
    ],
)
def test_workspace_limits_block_changes_only_in_the_live_workspace(environment, is_write, blocked):
    limits = AgentLimits(live_read_only=True)
    with patch.object(limits_mod, "action_is_write", return_value=is_write):
        if blocked:
            with pytest.raises(AgentGuardrailLimitError) as exc:
                check_agent_limits(
                    limits, org_id="o", agent_id="a", action="hubspot.contacts.create", environment_name=environment
                )
            assert exc.value.code == "AGENT_LIVE_WORKSPACE_READ_ONLY"
        else:
            check_agent_limits(
                limits, org_id="o", agent_id="a", action="hubspot.contacts.create", environment_name=environment
            )


def test_blocked_live_write_does_not_spend_the_hourly_budget():
    limits = AgentLimits(max_actions_per_hour=1, live_read_only=True)
    with patch.object(limits_mod, "action_is_write", return_value=True):
        with pytest.raises(AgentGuardrailLimitError):
            check_agent_limits(limits, org_id="o", agent_id="budget", action="x.create", environment_name="production")
    with patch.object(limits_mod, "action_is_write", return_value=False):
        check_agent_limits(limits, org_id="o", agent_id="budget", action="x.list", environment_name="production")


def _client_with_agent(row: dict | None) -> MagicMock:
    client = MagicMock()
    chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value
    chain.execute.return_value = SimpleNamespace(data=[row] if row else [])
    return client


def test_enforce_skips_synthetic_and_missing_agents():
    client = _client_with_agent({"guardrails": ["Slow down"], "config": {"guardrail_limits": {"max_actions_per_hour": 1}}})
    enforce_agent_guardrail_limits(SimpleNamespace(agent_id="synthetic-default", client=client, org_id="o"), "a.b")
    enforce_agent_guardrail_limits(SimpleNamespace(agent_id=None, client=client, org_id="o"), "a.b")
    client.table.assert_not_called()


def test_enforce_reads_the_agent_once_and_applies_its_limit():
    client = _client_with_agent({"guardrails": ["Slow down"], "config": {"guardrail_limits": {"max_actions_per_hour": 1}}})
    ctx = SimpleNamespace(agent_id=AGENT_ID, client=client, org_id="org-enforce", environment_name="production")
    enforce_agent_guardrail_limits(ctx, "hubspot.contacts.search")
    with pytest.raises(AgentGuardrailLimitError):
        enforce_agent_guardrail_limits(ctx, "hubspot.contacts.search")
    assert client.table.call_count == 1


def test_lookup_failure_does_not_block_tools():
    client = MagicMock()
    client.table.side_effect = RuntimeError("db down")
    ctx = SimpleNamespace(agent_id=AGENT_ID, client=client, org_id="org-fail", environment_name="production")
    enforce_agent_guardrail_limits(ctx, "hubspot.contacts.create")


def test_invoke_tool_returns_a_failed_result_when_an_agent_limit_is_hit():
    ctx = ToolContext(
        settings=SimpleNamespace(
            disable_connectors=False,
            connector_secrets_encryption_key="k" * 32,
            private_connector_runtime_enabled=True,
        ),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id=AGENT_ID,
    )
    error = AgentGuardrailLimitError("limit hit", code="AGENT_RATE_LIMITED")
    with patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits", side_effect=error):
        with patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda _c, _a, p: p):
            with patch("app.services.tool_service.write_audit_event") as audit:
                with patch("app.services.tool_service.send_slack_message") as send:
                    result = invoke_tool(ctx, "slack.post_message", {"channel": "#general", "message": "hi"})
    assert result.success is False
    assert result.error_code == "AGENT_RATE_LIMITED"
    send.assert_not_called()
    assert audit.call_args.kwargs["action"] == "tool.invoke.failed"
