"""Tests for priority workflow_schema batch 75 (third 25)."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.connectors.action_catalog.workflow_schemas_batch_75 import (
    BATCH_75_ACTION_KEYS,
    WORKFLOW_SCHEMAS_BATCH_75,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import validate_connector_plan
from app.services.connector_allowlists import PENDING_WORKFLOW_SCHEMA_ALLOWLIST


@pytest.mark.parametrize("action_key", BATCH_75_ACTION_KEYS)
def test_batch_75_schema_registered(action_key: str):
    assert action_key in WORKFLOW_SCHEMAS_BATCH_75
    assert get_workflow_schema(action_key) is not None


@pytest.mark.parametrize("action_key", BATCH_75_ACTION_KEYS)
def test_batch_75_removed_from_pending_allowlist(action_key: str):
    assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_batch_75_pending_allowlist_count():
    assert len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST) <= 93


def test_google_workspace_examples_migrated():
    for action_key in (
        "google_calendar.events.delete",
        "google_sheets.values.update",
        "gmail.drafts.create",
        "google_drive.permissions.create",
    ):
        assert get_workflow_schema(action_key) is not None
        assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_gmail_draft_requires_recipient_subject_body():
    plan = ConnectorActionPlan(
        tool_name="gmail_drafts_create",
        invoke_action="gmail.drafts.create",
        integration="gmail",
        kind="write",
        label="Create Gmail draft",
        args={"to": "alex@example.com"},
    )
    check = validate_connector_plan(plan, "Draft an email to alex")
    assert check is not None
    assert "subject" in check.missing
    assert "body" in check.missing


def test_airtable_create_requires_base_table_fields():
    plan = ConnectorActionPlan(
        tool_name="airtable_records_create",
        invoke_action="airtable.records.create",
        integration="airtable",
        kind="write",
        label="Create Airtable records",
        args={"base_id": "app123", "table": "Tasks"},
    )
    check = validate_connector_plan(plan, "Add a row to Airtable")
    assert check is not None
    assert "record fields" in check.missing
