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


def test_monday_task_does_not_map_to_automations_trigger():
    """F4 class: work-item noun must not lose to automations.* sibling."""
    match = get_chat_action_mapper().match_segment(
        'Create a task in Monday called "Follow up"',
        connected_integrations=["monday"],
    )
    assert match is not None
    assert match.entry.action_key == "monday.items.create"
    assert "automations" not in match.entry.action_key


def test_monday_item_create_phrasing():
    match = get_chat_action_mapper().match_segment(
        "create a Monday.com item for onboarding",
        connected_integrations=["monday"],
    )
    assert match is not None
    assert match.entry.action_key == "monday.items.create"


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


def test_maps_asana_task_for_person_with_due_date():
    match = get_chat_action_mapper().match_segment(
        "Create a task in Asana for Sarah to review the landing page by Friday",
        connected_integrations=["asana"],
    )
    assert match is not None
    assert match.entry.registry_key == "asana.tasks.create"
    assert match.args.get("name") == "review the landing page"
    assert match.args.get("assignee_hint") == "Sarah"
    assert match.args.get("due_on")


def test_maps_asana_task_assignee_only_without_invented_title():
    match = get_chat_action_mapper().match_segment(
        "Create an Asana task for Sarah",
        connected_integrations=["asana"],
    )
    assert match is not None
    assert match.args.get("assignee_hint") == "Sarah"
    assert "name" not in match.args or not match.args.get("name")


def test_apollo_list_intent_is_connector_intent():
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    assert ChatConnectorExecutionService.is_connector_intent(
        "Create a group in Apollo for MSPs",
        {},
    )


def test_maps_apollo_list_create():
    match = get_chat_action_mapper().match_segment(
        "Create a contact list in Apollo for MSP prospects",
        connected_integrations=["apollo"],
    )
    assert match is not None
    assert match.entry.action_key == "apollo.lists.create"
    assert match.args.get("name") == "MSP prospects"


def test_maps_apollo_segment_create_for_msps():
    match = get_chat_action_mapper().match_segment(
        "can you create a segment in Apollo for MSPs?",
        connected_integrations=["apollo"],
    )
    assert match is not None
    assert match.entry.action_key == "apollo.lists.create"
    assert match.args.get("name") == "MSP Prospects"


def test_maps_hubspot_static_list_msps():
    match = get_chat_action_mapper().match_segment(
        "Create HubSpot static list MSPs",
        connected_integrations=["hubspot"],
    )
    assert match is not None
    assert match.entry.action_key == "hubspot.lists.create"
    assert match.args.get("name") == "MSPs"
    assert match.args.get("object_type_id") == "0-1"
    assert match.args.get("processing_type") == "MANUAL"


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


def test_sta305_slack_draft_not_list_channels():
    """STA-305: draft lexicon + catalog-kind — never crown List channels."""
    match = get_chat_action_mapper().match_segment(
        "draft a follow-up in Slack for approval",
        connected_integrations=["slack"],
    )
    assert match is not None
    assert "post_message" in match.entry.registry_key
    assert "list" not in match.entry.action_key


def test_google_ads_structure_create_preferred_over_accounts_list():
    match = get_chat_action_mapper().match_segment(
        "Create a Google Ads Search campaign structure with 4 campaigns and ad groups.",
        connected_integrations=["google_ads"],
    )
    assert match is not None
    assert "structure.create" in match.entry.action_key
    assert "accounts.list" not in match.entry.action_key


def test_sta305_asana_omit_title_prefers_tasks_create():
    match = get_chat_action_mapper().match_segment(
        "Create an Asana task.",
        connected_integrations=["asana"],
    )
    assert match is not None
    assert match.entry.registry_key == "asana.tasks.create"
    assert "stories" not in match.entry.action_key


def test_sta305_jira_omit_fields_prefers_issues_create():
    match = get_chat_action_mapper().match_segment(
        "Create a Jira issue.",
        connected_integrations=["jira"],
    )
    assert match is not None
    assert "issues.create" in match.entry.action_key
    assert "update" not in match.entry.action_key


def test_sta305_gmail_send_not_drafts_lookalike():
    match = get_chat_action_mapper().match_segment(
        "Send an email via Gmail.",
        connected_integrations=["gmail"],
    )
    assert match is not None
    assert match.entry.registry_key == "gmail.messages.send"


def test_sta305_apollo_omit_name_prefers_lists_create():
    match = get_chat_action_mapper().match_segment(
        "In Apollo, create a contact list.",
        connected_integrations=["apollo"],
    )
    assert match is not None
    assert match.entry.action_key == "apollo.lists.create"
    assert "list" not in match.entry.action_key.split("lists.")[-1] or "create" in match.entry.action_key


def test_sta305_hubspot_contact_create_omit_name():
    match = get_chat_action_mapper().match_segment(
        "Create a HubSpot contact.",
        connected_integrations=["hubspot"],
    )
    assert match is not None
    assert match.entry.registry_key == "hubspot.contacts.create"


def test_sta305_github_omit_title_prefers_issues_create():
    """STA-305 class: bare GitHub issue create must not crown comment/list."""
    match = get_chat_action_mapper().match_segment(
        "Create a GitHub issue.",
        connected_integrations=["github"],
    )
    assert match is not None
    assert "issues.create" in match.entry.action_key
    assert "comment" not in match.entry.action_key
    assert "list" not in match.entry.action_key


def test_sta305_github_titled_issue_prefers_create():
    match = get_chat_action_mapper().match_segment(
        'Create a GitHub issue titled "Fix login timeout".',
        connected_integrations=["github"],
    )
    assert match is not None
    assert "issues.create" in match.entry.action_key


def test_sta305_jira_titled_issue_prefers_create():
    match = get_chat_action_mapper().match_segment(
        "Create a Jira issue titled Bug.",
        connected_integrations=["jira"],
    )
    assert match is not None
    assert "issues.create" in match.entry.action_key
    assert "update" not in match.entry.action_key


def test_sta305_hubspot_contact_list_phrase_not_contacts_search():
    """Write-ish HubSpot create contact must beat search lookalikes."""
    match = get_chat_action_mapper().match_segment(
        "Create a HubSpot contact for Acme.",
        connected_integrations=["hubspot"],
    )
    assert match is not None
    assert "contacts.create" in match.entry.action_key
    assert "search" not in match.entry.action_key


def test_sta305_asana_named_task_still_tasks_create():
    match = get_chat_action_mapper().match_segment(
        "Create an Asana task named Review.",
        connected_integrations=["asana"],
    )
    assert match is not None
    assert match.entry.registry_key == "asana.tasks.create"
    assert "stories" not in match.entry.action_key
