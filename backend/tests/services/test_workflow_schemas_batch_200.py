"""Tests for Ahrefs write workflow_schema batch 200."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.connectors.action_catalog.workflow_schemas_batch_200 import (
    BATCH_200_ACTION_KEYS,
    WORKFLOW_SCHEMAS_BATCH_200,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import validate_connector_plan
from app.services.connector_allowlists import PENDING_WORKFLOW_SCHEMA_ALLOWLIST


@pytest.mark.parametrize("action_key", BATCH_200_ACTION_KEYS)
def test_batch_200_schema_registered(action_key: str):
    assert action_key in WORKFLOW_SCHEMAS_BATCH_200
    assert get_workflow_schema(action_key) is not None


@pytest.mark.parametrize("action_key", BATCH_200_ACTION_KEYS)
def test_batch_200_removed_from_pending_allowlist(action_key: str):
    assert action_key not in PENDING_WORKFLOW_SCHEMA_ALLOWLIST


def test_batch_200_pending_allowlist_empty():
    assert len(PENDING_WORKFLOW_SCHEMA_ALLOWLIST) == 0


def test_ahrefs_projects_create_requires_name_and_url():
    plan = ConnectorActionPlan(
        tool_name="ahrefs_projects_create",
        invoke_action="ahrefs.projects.create",
        integration="ahrefs",
        kind="write",
        label="Create Ahrefs project",
        args={"name": "Demo"},
    )
    check = validate_connector_plan(plan, "Create Ahrefs project")
    assert check is not None
    assert "project url" in check.missing
