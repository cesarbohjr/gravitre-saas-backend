"""Module B Phase 2 — schema-constrained parameter extraction."""
from __future__ import annotations

import pytest

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.parameter_ledger import ingest_message_slots, stage_awaiting_params
from app.services.schema_param_extractor import (
    enrich_plan_args_from_schema,
    extract_action_args_heuristic,
)


def test_jira_heuristic_extracts_summary_and_project_without_quotes():
    args = extract_action_args_heuristic(
        "jira.issues.create",
        "create an issue login page broken in project ENG",
    )
    assert args.get("project_key", "").upper() == "ENG"
    assert "login" in (args.get("summary") or "").lower()


def test_jira_followup_title_from_plain_text():
    args = extract_action_args_heuristic(
        "jira.issues.create",
        "Checkout button fails on mobile",
        existing_args={"project_key": "ENG"},
    )
    assert "checkout" in (args.get("summary") or "").lower()
    assert args.get("project_key") == "ENG"


def test_gmail_heuristic_uses_ledger_email():
    ledger = ingest_message_slots("alex@acme.com said hello yesterday")
    args = extract_action_args_heuristic(
        "gmail.messages.send",
        "send an email about the renewal",
        ledger=ledger,
    )
    assert args.get("to") == "alex@acme.com"


@pytest.mark.asyncio
async def test_enrich_plan_skips_model_when_complete():
    plan = ConnectorActionPlan(
        tool_name="jira_create",
        invoke_action="jira.issues.create",
        integration="jira",
        kind="write",
        label="Create issue",
        args={},
    )
    enriched, patch = await enrich_plan_args_from_schema(
        plan,
        'create an issue titled "Broken checkout" in project ENG',
        use_model=False,
    )
    assert enriched.args.get("project_key", "").upper() == "ENG"
    assert "Broken checkout" in (enriched.args.get("summary") or "")
    assert patch.get("parameter_ledger")


def test_zendesk_heuristic_extracts_subject_without_quotes():
    args = extract_action_args_heuristic(
        "zendesk.tickets.create",
        "create a zendesk ticket about Checkout fails on mobile for VIP accounts",
    )
    assert "checkout" in (args.get("subject") or "").lower()
    assert args.get("comment") or args.get("body") or args.get("description")


def test_monday_heuristic_extracts_item_name_and_board():
    args = extract_action_args_heuristic(
        "monday.items.create",
        "create an item called Renewals follow-up on board sales123",
    )
    assert "renewals" in (args.get("item_name") or args.get("name") or "").lower()
    assert args.get("board_id") == "sales123"


def test_clickup_heuristic_extracts_task_name_and_list():
    args = extract_action_args_heuristic(
        "clickup.tasks.create",
        "create a task called Mobile checkout bug in list eng-triage",
    )
    assert "checkout" in (args.get("name") or "").lower()
    assert args.get("list_id") == "eng-triage"


def test_github_notion_pipedrive_spotcheck_schema_primary():
    """Three connectors never named in Module B history before this fix pass."""
    gh = extract_action_args_heuristic(
        "github.issues.create",
        "create a github issue titled Auth token refresh fails",
    )
    assert "auth" in (gh.get("title") or "").lower()

    notion = extract_action_args_heuristic(
        "notion.pages.create",
        'create a notion page called "Q3 renewals brief"',
    )
    assert "renewals" in (notion.get("title") or notion.get("name") or "").lower()

    pd = extract_action_args_heuristic(
        "pipedrive.deals.create",
        "title is Checkout fails on mobile for VIP accounts priority urgent",
    )
    assert "checkout" in (pd.get("title") or "").lower()


def test_jira_stage_resume_multi_turn():
    plan = ConnectorActionPlan(
        tool_name="jira_create",
        invoke_action="jira.issues.create",
        integration="jira",
        kind="write",
        label="Create issue",
        args={},
    )
    patch = stage_awaiting_params(plan, ("summary", "project key"))
    from app.services.parameter_ledger import resume_awaiting_params

    task_state = {**patch, "recent_user_messages": ["create an issue"]}
    # Provide title + project in follow-up without quotes.
    resumed, _, _ = resume_awaiting_params(
        "title is Checkout button fails project ENG",
        task_state,
    )
    assert resumed is not None
    # Resume fills free-text; heuristic extract helps project on process_turn.
    filled = extract_action_args_heuristic(
        "jira.issues.create",
        "title is Checkout button fails project ENG",
        existing_args=dict(resumed.args or {}),
    )
    assert filled.get("project_key", "").upper() == "ENG"
    assert "checkout" in (filled.get("summary") or "").lower()
