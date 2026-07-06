"""ReAct-first connector routing tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.connector_chat_routing import (
    has_pending_connector_task,
    react_invoked_connector_tools,
    should_attempt_connector_fallback,
    should_run_connector_preflight,
)


def test_preflight_only_for_pending_connector_tasks():
    assert should_run_connector_preflight(None) is False
    assert should_run_connector_preflight({}) is False
    assert should_run_connector_preflight({"pending_task": {"type": "connector_action"}}) is True
    assert should_run_connector_preflight({"pending_task": {"type": "connector_orchestration"}}) is True
    assert should_run_connector_preflight({"pending_task": {"type": "general"}}) is False


def test_react_invoked_connector_tools_ignores_assistant_tools():
    result = SimpleNamespace(
        tool_calls=[
            {"tool": "assistant_analytics"},
            {"name": "web_search"},
        ]
    )
    assert react_invoked_connector_tools(result) is False

    result = SimpleNamespace(tool_calls=[{"tool": "hubspot.contacts.search"}])
    assert react_invoked_connector_tools(result) is True


def test_fallback_skipped_when_react_already_called_connector():
    react = SimpleNamespace(tool_calls=[{"tool": "slack.post_message"}])
    assert (
        should_attempt_connector_fallback(
            task_state={},
            react_result=react,
            message="post to slack",
            connected_integrations=["slack"],
        )
        is False
    )


def test_fallback_skipped_without_connected_integrations():
    assert (
        should_attempt_connector_fallback(
            task_state={},
            react_result=None,
            message="search hubspot contacts",
            connected_integrations=[],
        )
        is False
    )


def test_fallback_skipped_for_pending_connector_task():
    assert (
        should_attempt_connector_fallback(
            task_state={"pending_task": {"type": "connector_action"}},
            react_result=None,
            message="yes proceed",
            connected_integrations=["hubspot"],
        )
        is False
    )


def test_fallback_when_connector_intent_and_no_react_tools(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.services.chat_connector_execution_service.ChatConnectorExecutionService.is_connector_intent",
        lambda message, task_state: True,
    )
    assert (
        should_attempt_connector_fallback(
            task_state={},
            react_result=None,
            message="find contacts in hubspot named acme",
            connected_integrations=["hubspot"],
        )
        is True
    )
