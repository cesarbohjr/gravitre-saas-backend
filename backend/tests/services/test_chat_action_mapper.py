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
        "Search HubSpot for contacts from Acme.",
        connected_integrations=["hubspot"],
    )
    assert match is not None
    assert "search" in match.entry.registry_key
    assert match.entry.kind == "read"
    assert "Acme" in str(match.args.get("query", ""))


def test_maps_asana_task_create():
    match = get_chat_action_mapper().match_segment(
        "Create a task in Asana for reviewing the Q3 campaign.",
        connected_integrations=["asana"],
    )
    assert match is not None
    assert match.entry.registry_key == "asana.tasks.create"
    assert "Q3" in str(match.args.get("name", ""))


def test_maps_asana_task_create_an_asana_task_phrasing():
    match = get_chat_action_mapper().match_segment(
        "Create an Asana task for reviewing the Q3 campaign.",
        connected_integrations=["asana"],
    )
    assert match is not None
    assert match.entry.registry_key == "asana.tasks.create"


def test_maps_asana_follow_up_tasks_in_asana():
    match = get_chat_action_mapper().match_segment(
        "Create follow-up tasks in Asana",
        connected_integrations=["asana"],
    )
    assert match is not None
    assert match.entry.registry_key == "asana.tasks.create"


def test_maps_hubspot_deal_stage_update():
    match = get_chat_action_mapper().match_segment(
        "Update those deal stages in HubSpot after approval.",
        connected_integrations=["hubspot"],
    )
    assert match is not None
    assert match.entry.registry_key in {"hubspot.deals.update", "hubspot.deals.update_stage"}


def test_maps_hubspot_contact_create_without_email():
    match = get_chat_action_mapper().match_segment(
        "Create a HubSpot contact from the top row after approval.",
        connected_integrations=["hubspot"],
    )
    assert match is not None
    assert match.entry.registry_key == "hubspot.contacts.create"


def test_maps_slack_post_for_approval():
    match = get_chat_action_mapper().match_segment(
        "Post this summary to Slack for approval.",
        connected_integrations=["slack"],
    )
    assert match is not None
    assert match.entry.registry_key == "slack.post_message"
    assert match.args.get("channel")
    assert match.args.get("message")


def test_maps_google_sheet_find():
    match = get_chat_action_mapper().match_segment(
        "Find a Google Sheet and summarize the rows.",
        connected_integrations=["google_drive"],
    )
    assert match is not None
    assert "files.list" in match.entry.action_key
    assert "spreadsheet" in str(match.args.get("query", ""))


def test_maps_hubspot_deal_create():
    match = get_chat_action_mapper().match_segment(
        "Create a HubSpot deal and ask for approval before saving.",
        connected_integrations=["hubspot"],
    )
    assert match is not None
    assert match.entry.registry_key == "hubspot.deals.create"
    assert match.args.get("properties", {}).get("dealname")


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
