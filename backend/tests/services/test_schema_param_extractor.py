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
