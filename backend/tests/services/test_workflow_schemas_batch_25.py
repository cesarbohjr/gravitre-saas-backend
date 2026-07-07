"""Tests for priority workflow_schema batch 25."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.connectors.action_catalog.workflow_schemas_batch_25 import (
    BATCH_25_ACTION_KEYS,
    WORKFLOW_SCHEMAS_BATCH_25,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import validate_connector_plan
from app.services.connector_allowlists import PENDING_WORKFLOW_SCHEMA_ALLOWLIST


@pytest.mark.parametrize("action_key", BATCH_25_ACTION_KEYS)
def test_batch_25_schema_registered(action_key: str):
    assert action_key in WORKFLOW_SCHEMAS_BATCH_25
    assert get_workflow_schema(action_key) is not None


@pytest.mark.parametrize("action_key", BATCH_25_ACTION_KEYS)
def test_batch_25_removed_from_pending_allowlist(action_key: str):
    assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_batch_25_pending_allowlist_shrank_from_baseline():
    assert len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST) <= 143


def test_hubspot_deal_create_requires_identity():
    plan = ConnectorActionPlan(
        tool_name="hubspot_deals_create",
        invoke_action="hubspot.deals.create",
        integration="hubspot",
        kind="write",
        label="Create HubSpot deal",
        args={},
    )
    check = validate_connector_plan(plan, "Create a HubSpot deal")
    assert check is not None
    assert "deal name" in check.missing


def test_gmail_send_complete_plan_passes():
    plan = ConnectorActionPlan(
        tool_name="gmail_messages_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail message",
        args={"to": "alex@example.com", "subject": "Hello", "body": "Follow up today"},
    )
    assert validate_connector_plan(plan, "Send Gmail to alex@example.com") is None


def test_jira_issue_create_requires_project_and_summary():
    plan = ConnectorActionPlan(
        tool_name="jira_issues_create",
        invoke_action="jira.issues.create",
        integration="jira",
        kind="write",
        label="Create Jira issue",
        args={"project_key": "ENG"},
    )
    check = validate_connector_plan(plan, "Create a Jira ticket")
    assert check is not None
    assert "summary" in check.missing
