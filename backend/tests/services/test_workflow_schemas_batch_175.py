"""Tests for priority workflow_schema batch 175 (final 18)."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.connectors.action_catalog.workflow_schemas_batch_175 import (
    BATCH_175_ACTION_KEYS,
    WORKFLOW_SCHEMAS_BATCH_175,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import validate_connector_plan
from app.services.connector_allowlists import PENDING_WORKFLOW_SCHEMA_ALLOWLIST


@pytest.mark.parametrize("action_key", BATCH_175_ACTION_KEYS)
def test_batch_175_schema_registered(action_key: str):
    assert action_key in WORKFLOW_SCHEMAS_BATCH_175
    assert get_workflow_schema(action_key) is not None


@pytest.mark.parametrize("action_key", BATCH_175_ACTION_KEYS)
def test_batch_175_removed_from_pending_allowlist(action_key: str):
    assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_batch_175_pending_allowlist_empty():
    assert len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST) == 0


def test_teams_and_payroll_examples_migrated():
    for action_key in (
        "microsoft_teams.messages.send",
        "plaid.public_token.exchange",
        "workday.timeoff.request",
        "stackadapt.campaigns.create",
    ):
        assert get_workflow_schema(action_key) is not None
        assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_teams_message_requires_channel_and_content():
    plan = ConnectorActionPlan(
        tool_name="microsoft_teams_messages_send",
        invoke_action="microsoft_teams.messages.send",
        integration="microsoft_teams",
        kind="write",
        label="Send Teams message",
        args={"team_id": "team-1"},
    )
    check = validate_connector_plan(plan, "Post to Teams channel")
    assert check is not None
    assert "channel id" in check.missing
    assert "message content" in check.missing
