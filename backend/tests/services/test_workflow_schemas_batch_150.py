"""Tests for priority workflow_schema batch 150 (sixth 25)."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.connectors.action_catalog.workflow_schemas_batch_150 import (
    BATCH_150_ACTION_KEYS,
    WORKFLOW_SCHEMAS_BATCH_150,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import validate_connector_plan
from app.services.connector_allowlists import PENDING_WORKFLOW_SCHEMA_ALLOWLIST


@pytest.mark.parametrize("action_key", BATCH_150_ACTION_KEYS)
def test_batch_150_schema_registered(action_key: str):
    assert action_key in WORKFLOW_SCHEMAS_BATCH_150
    assert get_workflow_schema(action_key) is not None


@pytest.mark.parametrize("action_key", BATCH_150_ACTION_KEYS)
def test_batch_150_removed_from_pending_allowlist(action_key: str):
    assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_batch_150_pending_allowlist_count():
    assert len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST) <= 18


def test_hr_and_legal_examples_migrated():
    for action_key in (
        "bamboohr.employees.create",
        "clio.matters.create",
        "email.send",
        "asana.stories.create",
    ):
        assert get_workflow_schema(action_key) is not None
        assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_email_send_requires_recipient_subject_body():
    plan = ConnectorActionPlan(
        tool_name="email_send",
        invoke_action="email.send",
        integration="email",
        kind="write",
        label="Send email",
        args={"to": "user@example.com"},
    )
    check = validate_connector_plan(plan, "Send an email")
    assert check is not None
    assert "subject" in check.missing
    assert "body" in check.missing
