"""QA-only unified-turn force-tool hooks."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.unified_turn_qa_hooks import (
    QA_FORCE_TOOL_HEADER,
    registry_tool_for_force,
    resolve_qa_force_tool,
)


def test_resolve_qa_force_tool_disabled_when_setting_off():
    settings = MagicMock(unified_turn_qa_hooks_enabled=False)
    assert resolve_qa_force_tool(settings, header_value="gmail.messages.batch") is None


def test_resolve_qa_force_tool_from_header():
    settings = MagicMock(unified_turn_qa_hooks_enabled=True)
    assert resolve_qa_force_tool(settings, header_value="gmail.messages.batch") == "gmail.messages.batch"


def test_resolve_qa_force_tool_from_env(monkeypatch):
    settings = MagicMock(unified_turn_qa_hooks_enabled=True)
    monkeypatch.setenv("UNIFIED_TURN_QA_FORCE_TOOL", "gmail.messages.send")
    assert resolve_qa_force_tool(settings, header_value=None) == "gmail.messages.send"


def test_registry_tool_for_force_accepts_invoke_action_and_name():
    from types import SimpleNamespace

    batch = SimpleNamespace(name="gmail_messages_batch", invoke_action="gmail.messages.batch")
    send = SimpleNamespace(name="gmail_messages_send", invoke_action="gmail.messages.send")
    registry = MagicMock(_specs={"gmail_messages_batch": batch, "gmail_messages_send": send})

    name, invoke, args = registry_tool_for_force(registry, "gmail.messages.batch")
    assert name == "gmail_messages_batch"
    assert invoke == "gmail.messages.batch"
    assert args == {}

    name2, invoke2, _ = registry_tool_for_force(registry, "gmail_messages_send")
    assert name2 == "gmail_messages_send"
    assert invoke2 == "gmail.messages.send"


def test_registry_tool_for_force_unknown_raises():
    registry = MagicMock(_specs={})
    with pytest.raises(ValueError, match="unknown QA force tool"):
        registry_tool_for_force(registry, "not.a.real.tool")


def test_qa_force_tool_header_constant():
    assert QA_FORCE_TOOL_HEADER == "X-Gravitre-QA-Force-Tool"
