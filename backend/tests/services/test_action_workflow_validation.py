"""Tests for schema-driven connector workflow validation."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import (
    clear_workflow_schema_registry,
    register_workflow_schema,
)
from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.connector_action_workflows import validate_connector_plan


@pytest.fixture(autouse=True)
def _clear_schema_registry():
    clear_workflow_schema_registry()
    yield
    clear_workflow_schema_registry()


def test_schema_only_action_flags_missing_fields():
    register_workflow_schema(
        "demo.tasks.create",
        ActionWorkflowSchema(
            intent_label="Create demo task",
            required_fields=(
                WorkflowFieldSpec("title", ("title",)),
                WorkflowFieldSpec("owner", ("owner_id",)),
            ),
            optional_fields=(WorkflowFieldSpec("Priority", ("priority",)),),
        ),
    )
    plan = ConnectorActionPlan(
        tool_name="demo_tasks_create",
        invoke_action="demo.tasks.create",
        integration="demo",
        kind="write",
        label="Create demo task",
        args={"priority": "high"},
    )
    check = validate_connector_plan(plan, "Create a demo task")
    assert check is not None
    assert "title" in check.missing
    assert "owner" in check.missing
    assert check.known.get("Priority") == "high"
