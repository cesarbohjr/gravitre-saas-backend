"""Declarative chat workflow schemas keyed by catalog action id."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

ASANA_TASKS_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Create Asana task",
    known_defaults=(("Task type", "Asana task"),),
    required_fields=(
        WorkflowFieldSpec(
            "task title",
            ("name",),
            validator="asana_task_title",
        ),
        WorkflowFieldSpec("project", ("project", "project_id")),
        WorkflowFieldSpec(
            "due date",
            ("due_on",),
            sensitive=True,
            inferrable=False,
        ),
    ),
    optional_fields=(
        WorkflowFieldSpec(
            "Assignee",
            ("assignee_hint", "assignee"),
            sensitive=True,
            inferrable=False,
        ),
    ),
)

APOLLO_LISTS_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Create Apollo contact list",
    required_fields=(WorkflowFieldSpec("list name", ("name", "list_name")),),
    optional_fields=(WorkflowFieldSpec("Modality", ("modality",)),),
)

HUBSPOT_CONTACTS_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Create HubSpot contact",
    required_fields=(
        WorkflowFieldSpec(
            "email or contact name",
            ("email", "firstname", "properties"),
            validator="hubspot_contact_identity",
        ),
    ),
    optional_fields=(
        WorkflowFieldSpec("First name", ("firstname",)),
        WorkflowFieldSpec("Last name", ("lastname",)),
    ),
)

SLACK_POST_MESSAGE_SCHEMA = ActionWorkflowSchema(
    intent_label="Post Slack message",
    required_fields=(
        WorkflowFieldSpec("channel", ("channel",)),
        WorkflowFieldSpec("message", ("text", "message")),
    ),
)

_TEST_SCHEMA_REGISTRY: dict[str, ActionWorkflowSchema] = {}


def register_workflow_schema(action_key: str, schema: ActionWorkflowSchema) -> None:
    """Register a workflow schema override (used in tests)."""
    _TEST_SCHEMA_REGISTRY[action_key.strip().lower()] = schema


def clear_workflow_schema_registry() -> None:
    _TEST_SCHEMA_REGISTRY.clear()


def get_workflow_schema(action_key: str) -> ActionWorkflowSchema | None:
    key = action_key.strip().lower()
    if key in _TEST_SCHEMA_REGISTRY:
        return _TEST_SCHEMA_REGISTRY[key]
    from app.connectors.action_catalog.workflow_schemas_batch_25 import WORKFLOW_SCHEMAS_BATCH_25

    if key in WORKFLOW_SCHEMAS_BATCH_25:
        return WORKFLOW_SCHEMAS_BATCH_25[key]
    from app.connectors.action_catalog.registry import get_action_spec

    spec = get_action_spec(key)
    if spec and spec.workflow_schema:
        return spec.workflow_schema
    return None


def list_non_inferrable_arg_keys(action_key: str) -> frozenset[str]:
    schema = get_workflow_schema(action_key)
    if not schema:
        return frozenset()
    keys: set[str] = set()
    for field in (*schema.required_fields, *schema.optional_fields):
        if field.sensitive or not field.inferrable:
            keys.update(field.arg_keys)
    return frozenset(keys)
