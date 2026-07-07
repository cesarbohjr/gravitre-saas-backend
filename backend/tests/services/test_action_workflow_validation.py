"""Tests for schema-driven connector workflow validation."""
from __future__ import annotations

import pytest

from app.connectors.action_catalog.action_workflow_schema import (
    clear_workflow_schema_registry,
    get_workflow_schema,
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


def test_hubspot_contacts_create_schema_requires_identity():
    schema = get_workflow_schema("hubspot.contacts.create")
    assert schema is not None
    plan = ConnectorActionPlan(
        tool_name="hubspot_contacts_create",
        invoke_action="hubspot.contacts.create",
        integration="hubspot",
        kind="write",
        label="Create HubSpot contact",
        args={},
    )
    check = validate_connector_plan(plan, "Create a HubSpot contact")
    assert check is not None
    assert "email or contact name" in check.missing

    complete = ConnectorActionPlan(
        tool_name="hubspot_contacts_create",
        invoke_action="hubspot.contacts.create",
        integration="hubspot",
        kind="write",
        label="Create HubSpot contact",
        args={"email": "alex@example.com", "firstname": "Alex"},
    )
    assert validate_connector_plan(complete, "Create HubSpot contact for alex@example.com") is None


def test_slack_post_message_schema_requires_channel_and_body():
    schema = get_workflow_schema("slack.post_message")
    assert schema is not None
    plan = ConnectorActionPlan(
        tool_name="slack_post_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Post Slack message",
        args={"channel": "#sales"},
    )
    check = validate_connector_plan(plan, "Notify #sales on Slack")
    assert check is not None
    assert "message" in check.missing

    complete = ConnectorActionPlan(
        tool_name="slack_post_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Post Slack message",
        args={"channel": "#sales", "message": "Pipeline update ready"},
    )
    assert validate_connector_plan(complete, "Post to #sales on Slack") is None
