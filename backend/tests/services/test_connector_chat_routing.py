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


def test_preflight_for_pending_connector_tasks():
    assert should_run_connector_preflight(None) is False
    assert should_run_connector_preflight({}) is False
    assert should_run_connector_preflight({"pending_task": {"type": "connector_action"}}) is True
    assert should_run_connector_preflight({"pending_task": {"type": "connector_orchestration"}}) is True
    assert should_run_connector_preflight({"pending_task": {"type": "general"}}) is False
    assert (
        should_run_connector_preflight(
            {"current_plan": {"goal": "Send Gmail message"}},
            message="cancel",
        )
        is True
    )


def test_preflight_skips_fresh_connector_intent_for_react_first():
    """Fresh single-connector asks must reach ReAct; pending tasks still preflight."""
    assert (
        should_run_connector_preflight(
            {},
            message="Create a task in Asana for Sarah to review the landing page by Friday",
        )
        is False
    )
    assert (
        should_run_connector_preflight(
            {},
            message="can you create a segment in Apollo for MSPs?",
        )
        is False
    )
    assert should_run_connector_preflight({}, message="hello there") is False
    assert (
        should_run_connector_preflight(
            {"pending_task": {"type": "connector_action", "status": "awaiting_confirm"}},
            message="yes",
        )
        is True
    )


def test_preflight_runs_for_fresh_multi_connector_orchestration():
    """STA-307 — HubSpot+Slack chip must preflight before connector_unavailable clarify."""
    message = (
        "Search HubSpot for high-intent leads and draft a follow-up in Slack for approval"
    )
    assert (
        should_run_connector_preflight(
            {},
            message=message,
            connected_integrations=[],
        )
        is True
    )


def test_preflight_skips_wave67_plan_before_tools_meta():
    """STA-325 — single-connector + meta plan clause must reach ReAct, not orch preflight."""
    message = (
        "Using Apollo, list my contact lists and summarize the first few names. "
        "Then outline a short plan before calling tools."
    )
    assert (
        should_run_connector_preflight(
            {},
            message=message,
            connected_integrations=["apollo", "slack"],
        )
        is False
    )


def test_preflight_skips_omit_name_list_create_despite_apollo_comma():
    """STA-305 parallel-path: omit-name create must not preflight as orchestration.

    \"In Apollo, create a contact list.\" splits on the comma and falsely trips
    is_orchestration_intent; prefer_connector must suppress preflight so the
    governed auto-plan (MSP Prospects / inferred_fields) can run.
    """
    message = "In Apollo, create a contact list."
    assert (
        should_run_connector_preflight(
            {},
            message=message,
            connected_integrations=["apollo", "hubspot", "slack"],
        )
        is False
    )
    # Pending orchestration still preflights (confirm/decline path).
    assert (
        should_run_connector_preflight(
            {"pending_task": {"type": "connector_orchestration", "status": "awaiting_plan_confirm"}},
            message=message,
            connected_integrations=["apollo"],
        )
        is True
    )


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
    react = SimpleNamespace(
        tool_calls=[{"tool": "slack.post_message", "result": {"success": True}}]
    )
    assert (
        should_attempt_connector_fallback(
            task_state={},
            react_result=react,
            message="post to slack",
            connected_integrations=["slack"],
        )
        is False
    )


def test_fallback_runs_when_react_connector_tools_failed():
    """Regression: failed apollo_lists_create must not block governed fallback."""
    react = SimpleNamespace(
        tool_calls=[
            {
                "tool": "apollo_lists_create",
                "args": {"name": "MSP Prospects"},
                "result": {
                    "success": False,
                    "error": 'invalid input syntax for type uuid: "synthetic-default"',
                },
            }
        ]
    )
    assert (
        should_attempt_connector_fallback(
            task_state={},
            react_result=react,
            message="can you create a segment in Apollo for MSPs?",
            connected_integrations=["apollo"],
        )
        is True
    )


def test_fallback_runs_without_connected_integrations_for_connector_intent():
    assert (
        should_attempt_connector_fallback(
            task_state={},
            react_result=None,
            message="Create a task in Asana for Sarah to review the landing page by Friday",
            connected_integrations=[],
        )
        is True
    )


def test_fallback_always_runs_for_pending_connector_task():
    """Phase A: pending family must reach process_turn for LLM classify — not regex-only."""
    assert (
        should_attempt_connector_fallback(
            task_state={"pending_task": {"type": "connector_action"}},
            react_result=None,
            message="actually never mind that write",
            connected_integrations=["hubspot"],
        )
        is True
    )
    assert (
        should_attempt_connector_fallback(
            task_state={"pending_task": {"type": "connector_action"}},
            react_result=None,
            message="yes proceed",
            connected_integrations=["hubspot"],
        )
        is True
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
