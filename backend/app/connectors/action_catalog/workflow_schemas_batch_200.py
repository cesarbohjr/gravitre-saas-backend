"""Ahrefs Management write-action workflow schemas."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

BATCH_200_ACTION_KEYS: tuple[str, ...] = (
    "ahrefs.projects.create",
    "ahrefs.rank_tracker.add",
)


def _req(label: str, *keys: str, validator: str | None = None) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, validator=validator)


def _opt(label: str, *keys: str) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys)


WORKFLOW_SCHEMAS_BATCH_200: dict[str, ActionWorkflowSchema] = {
    "ahrefs.projects.create": ActionWorkflowSchema(
        intent_label="Create Ahrefs project",
        required_fields=(
            _req("project name", "name", "title", "properties", validator="named_or_payload"),
            _req("project url", "url", "project_url"),
        ),
        optional_fields=(
            _opt("Protocol", "protocol"),
            _opt("Mode", "mode"),
        ),
    ),
    "ahrefs.rank_tracker.add": ActionWorkflowSchema(
        intent_label="Add Ahrefs rank tracker keywords",
        required_fields=(
            _req("project id", "project_id", "project"),
            _req("keywords list", "keywords", "payload", validator="list_or_object_payload"),
        ),
        optional_fields=(_opt("Locations", "locations"),),
    ),
}
