"""Tests for priority workflow_schema batch 100 (fourth 25)."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.connectors.action_catalog.workflow_schemas_batch_100 import (
    BATCH_100_ACTION_KEYS,
    WORKFLOW_SCHEMAS_BATCH_100,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import validate_connector_plan
from app.services.connector_allowlists import PENDING_WORKFLOW_SCHEMA_ALLOWLIST


@pytest.mark.parametrize("action_key", BATCH_100_ACTION_KEYS)
def test_batch_100_schema_registered(action_key: str):
    assert action_key in WORKFLOW_SCHEMAS_BATCH_100
    assert get_workflow_schema(action_key) is not None


@pytest.mark.parametrize("action_key", BATCH_100_ACTION_KEYS)
def test_batch_100_removed_from_pending_allowlist(action_key: str):
    assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_batch_100_pending_allowlist_count():
    assert len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST) <= 68


def test_finance_and_analytics_examples_migrated():
    for action_key in (
        "quickbooks.invoices.create",
        "xero.contacts.create",
        "segment.track",
        "microsoft365.teams.messages.send",
    ):
        assert get_workflow_schema(action_key) is not None
        assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_teams_message_requires_channel_and_content():
    plan = ConnectorActionPlan(
        tool_name="microsoft365_teams_messages_send",
        invoke_action="microsoft365.teams.messages.send",
        integration="microsoft365",
        kind="write",
        label="Send Teams message",
        args={"team_id": "team-1"},
    )
    check = validate_connector_plan(plan, "Post to Teams channel")
    assert check is not None
    assert "channel id" in check.missing
    assert "message" in check.missing
