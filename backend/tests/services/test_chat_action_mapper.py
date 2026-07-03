"""Tests for chat action mapper."""
from __future__ import annotations

from app.services.chat_action_mapper import get_chat_action_mapper


def test_maps_monday_task_create():
    match = get_chat_action_mapper().match_segment(
        'Create a task in Monday called "Follow up stale deal"',
        connected_integrations=["monday"],
    )
    assert match is not None
    assert match.entry.action_key == "monday.items.create"
    assert match.args.get("item_name")


def test_maps_slack_notify():
    match = get_chat_action_mapper().match_segment(
        'Post "Weekly summary" to #sales in Slack',
        connected_integrations=["slack"],
    )
    assert match is not None
    assert "slack.post_message" in match.entry.registry_key
    assert match.args.get("message")


def test_maps_hubspot_search():
    match = get_chat_action_mapper().match_segment(
        "Search HubSpot for contacts at Acme",
        connected_integrations=["hubspot"],
    )
    assert match is not None
    assert "search" in match.entry.registry_key
    assert match.entry.kind == "read"


def test_gmail_send_requires_args():
    match = get_chat_action_mapper().match_segment(
        'Send Gmail follow-up to user@example.com with subject "Hello" and body "Checking in"',
        connected_integrations=["gmail"],
    )
    assert match is not None
    assert match.entry.registry_key == "gmail.messages.send"
    assert match.entry.requires_approval is True


def test_missing_connector_skip_reason():
    reason = get_chat_action_mapper().skip_reason(
        "Create a task in Monday",
        connected_integrations=["hubspot"],
    )
    assert reason is not None
    assert "Connect" in reason
