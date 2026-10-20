"""Equivalent external sends need the same approval, whichever connector sends."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.f1_write_slice import requires_write_approval_always
from app.services.catalog_write_authority import mcp_tool_requires_write_approval
from app.services.mcp_client_service import resolve_mcp_tool_authority
from app.services.write_capability import EXTERNAL_SEND, capability_of_action, capability_of_mcp_tool
from app.services.write_governance import resolve_write_user_approval

SENDS = [
    "gmail.messages.send",
    "outlook.messages.send",
    "microsoft365.mail.send",
    "microsoft365.batch.mail",
    "sendgrid.mail.send",
    "microsoft_teams.messages.send",
    "slack.post_message",
    "webhook.post",
    "zendesk.tickets.reply",
    "intercom.conversations.reply",
]
NOT_SENDS = [
    "hubspot.contacts.search",
    "gmail.messages.list",
    "outlook.messages.list",
    "freshservice.tickets.get",
    "asana.tasks.create",
    "sendgrid.stats.get",
]


@pytest.mark.parametrize("action", SENDS)
def test_every_send_is_an_external_send_and_always_needs_approval(action):
    assert capability_of_action(action) == EXTERNAL_SEND
    assert requires_write_approval_always(action) is True


@pytest.mark.parametrize("action", NOT_SENDS)
def test_reads_and_internal_writes_are_not_sends(action):
    assert capability_of_action(action) is None


class _Identity:
    trust_level = "autonomous"
    approval_rule_overrides = {"write": "auto_run"}


@pytest.mark.parametrize("action", ["outlook.messages.send", "sendgrid.mail.send", "webhook.post"])
def test_autonomous_auto_run_agent_still_needs_approval_for_any_send(action, monkeypatch):
    import app.services.write_governance as wg

    monkeypatch.setattr(wg, "resolve_approval_override", lambda identity, kind: "auto_run")
    needs, reason = resolve_write_user_approval(
        is_write=True, invoke_action=action, action_kind="write", hitl=None, identity=_Identity(), rules=None
    )
    assert needs is True and "always" in reason


@pytest.mark.parametrize("name", ["send_email", "gmail_send_message", "slack_post_message", "reply_all", "post_webhook"])
def test_mcp_send_tools_need_approval_even_when_the_server_says_read_only(name):
    assert capability_of_mcp_tool(name) == EXTERNAL_SEND
    assert mcp_tool_requires_write_approval(capability_tier="read", read_only_hint=True, tool_name=name) is True
    tier, requires, *_ = resolve_mcp_tool_authority(name, "", {"annotations": {"readOnlyHint": True}})
    assert tier == "write" and requires is True


def test_read_only_hint_cannot_downgrade_a_gravitre_write():
    assert mcp_tool_requires_write_approval(capability_tier="write", read_only_hint=True, tool_name="create_record") is True


def test_read_only_tool_stays_read():
    assert mcp_tool_requires_write_approval(capability_tier="read", read_only_hint=True, tool_name="list_records") is False
    assert capability_of_mcp_tool("search_messages") is None
