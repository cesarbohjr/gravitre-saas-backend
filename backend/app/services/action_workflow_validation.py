"""Generic chat workflow validation from catalog action schemas."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.execution_envelope import format_operator_response

FieldValidator = Callable[[dict[str, Any], WorkflowFieldSpec], bool]


@dataclass(frozen=True)
class WorkflowCheck:
    status: str
    message: str
    missing: tuple[str, ...] = ()
    known: dict[str, str] = field(default_factory=dict)
    candidates: tuple[str, ...] = ()
    dialogue_mode: str = "answer"
    updated_plan: ConnectorActionPlan | None = None


FIELD_VALIDATORS: dict[str, FieldValidator] = {}


def _validator_asana_task_title(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    name = str(args.get("name") or "").strip()
    assignee_hint = str(args.get("assignee_hint") or "").strip()
    return bool(name) and name.lower() != assignee_hint.lower()


FIELD_VALIDATORS["asana_task_title"] = _validator_asana_task_title


def _validator_hubspot_contact_identity(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    if str(args.get("email") or "").strip():
        return True
    if str(args.get("firstname") or "").strip() or str(args.get("lastname") or "").strip():
        return True
    properties = args.get("properties")
    if isinstance(properties, dict):
        return any(str(value or "").strip() for value in properties.values())
    return False


FIELD_VALIDATORS["hubspot_contact_identity"] = _validator_hubspot_contact_identity


def _field_present(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    if field.validator:
        validator = FIELD_VALIDATORS.get(field.validator)
        if validator:
            return validator(args, field)
    return any(str(args.get(key) or "").strip() for key in field.arg_keys)


def _optional_known_value(args: dict[str, Any], field: WorkflowFieldSpec) -> str | None:
    for key in field.arg_keys:
        value = str(args.get(key) or "").strip()
        if value:
            return value
    return None


def validate_plan_against_schema(
    plan: ConnectorActionPlan,
    schema: ActionWorkflowSchema,
) -> WorkflowCheck | None:
    args = dict(plan.args or {})
    missing: list[str] = []
    known: dict[str, str] = {label: value for label, value in schema.known_defaults}

    for field in schema.optional_fields:
        value = _optional_known_value(args, field)
        if value:
            known[field.label] = value

    for field in schema.required_fields:
        if not _field_present(args, field):
            missing.append(field.label)

    if not missing:
        return None

    return WorkflowCheck(
        status="needs clarification",
        missing=tuple(missing),
        known=known,
        dialogue_mode="clarify",
        message=format_operator_response(
            intent=schema.intent_label,
            status="needs clarification",
            matched_action=plan.invoke_action,
            planned=known,
            missing_parameters=missing,
            next_step="Reply with the missing details (task title, project, and due date)."
            if plan.invoke_action == "asana.tasks.create"
            else "Reply with the missing details for this action.",
        ),
    )
