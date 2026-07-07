"""Tests for priority workflow_schema batch 125 (fifth 25)."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.connectors.action_catalog.workflow_schemas_batch_125 import (
    BATCH_125_ACTION_KEYS,
    WORKFLOW_SCHEMAS_BATCH_125,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import validate_connector_plan
from app.services.connector_allowlists import PENDING_WORKFLOW_SCHEMA_ALLOWLIST


@pytest.mark.parametrize("action_key", BATCH_125_ACTION_KEYS)
def test_batch_125_schema_registered(action_key: str):
    assert action_key in WORKFLOW_SCHEMAS_BATCH_125
    assert get_workflow_schema(action_key) is not None


@pytest.mark.parametrize("action_key", BATCH_125_ACTION_KEYS)
def test_batch_125_removed_from_pending_allowlist(action_key: str):
    assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_batch_125_pending_allowlist_count():
    assert len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST) == 43


def test_data_platform_examples_migrated():
    for action_key in (
        "mongodb.documents.insert",
        "postgresql.query.update",
        "snowflake.stages.put",
        "mixpanel.events.track",
    ):
        assert get_workflow_schema(action_key) is not None
        assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_apollo_sequence_add_requires_sequence_and_contacts():
    plan = ConnectorActionPlan(
        tool_name="apollo_sequences_add",
        invoke_action="apollo.sequences.add",
        integration="apollo",
        kind="write",
        label="Add to Apollo sequence",
        args={"sequence_id": "seq-1"},
    )
    check = validate_connector_plan(plan, "Add leads to sequence")
    assert check is not None
    assert "contact ids" in check.missing
