"""Tests for priority workflow_schema batch 50 (second 25)."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.connectors.action_catalog.workflow_schemas_batch_50 import (
    BATCH_50_ACTION_KEYS,
    WORKFLOW_SCHEMAS_BATCH_50,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import validate_connector_plan
from app.services.connector_allowlists import PENDING_WORKFLOW_SCHEMA_ALLOWLIST


@pytest.mark.parametrize("action_key", BATCH_50_ACTION_KEYS)
def test_batch_50_schema_registered(action_key: str):
    assert action_key in WORKFLOW_SCHEMAS_BATCH_50
    assert get_workflow_schema(action_key) is not None


@pytest.mark.parametrize("action_key", BATCH_50_ACTION_KEYS)
def test_batch_50_removed_from_pending_allowlist(action_key: str):
    assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_batch_50_pending_allowlist_count():
    assert len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST) <= 118


def test_user_examples_migrated():
    for action_key in (
        "hubspot.deals.delete",
        "slack.conversations.create",
        "stripe.customers.create",
        "sendgrid.mail.send",
        "outlook.messages.send",
    ):
        assert get_workflow_schema(action_key) is not None
        assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_outlook_send_requires_recipient_subject_body():
    plan = ConnectorActionPlan(
        tool_name="outlook_messages_send",
        invoke_action="outlook.messages.send",
        integration="outlook",
        kind="write",
        label="Send Outlook message",
        args={"to": "alex@example.com"},
    )
    check = validate_connector_plan(plan, "Send Outlook email")
    assert check is not None
    assert "subject" in check.missing
    assert "body" in check.missing


def test_webhook_post_requires_payload():
    plan = ConnectorActionPlan(
        tool_name="webhook_post",
        invoke_action="webhook.post",
        integration="webhook",
        kind="write",
        label="POST webhook payload",
        args={},
    )
    check = validate_connector_plan(plan, "POST to webhook")
    assert check is not None
    assert "payload" in check.missing
