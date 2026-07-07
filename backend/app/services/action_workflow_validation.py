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


def _dict_has_content(value: object) -> bool:
    return isinstance(value, dict) and any(str(item or "").strip() for item in value.values())


def _validator_hubspot_deal_create(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    if str(args.get("dealname") or "").strip():
        return True
    return _dict_has_content(args.get("properties"))


def _validator_hubspot_properties_payload(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    return _dict_has_content(args.get("properties"))


def _validator_jira_issue_ref(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    return any(str(args.get(key) or "").strip() for key in ("issue_key", "issue_id"))


def _validator_jira_update_payload(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    if _dict_has_content(args.get("fields")):
        return True
    return any(str(args.get(key) or "").strip() for key in ("summary", "description"))


def _validator_named_or_payload(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    for key in field.arg_keys:
        value = args.get(key)
        if isinstance(value, dict):
            if _dict_has_content(value):
                return True
        elif str(value or "").strip():
            return True
    return False


def _validator_zendesk_ticket_body(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    return any(str(args.get(key) or "").strip() for key in ("comment", "body", "description"))


def _validator_salesforce_task_subject(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    fields = args.get("fields")
    if isinstance(fields, dict):
        subject = fields.get("Subject") or fields.get("subject")
        if str(subject or "").strip():
            return True
    return str(args.get("subject") or "").strip()


def _validator_asana_task_update(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    for key in ("name", "due_on", "assignee", "assignee_hint", "notes"):
        if str(args.get(key) or "").strip():
            return True
    return _dict_has_content(args.get("payload"))


FIELD_VALIDATORS["hubspot_deal_create"] = _validator_hubspot_deal_create
FIELD_VALIDATORS["hubspot_properties_payload"] = _validator_hubspot_properties_payload
FIELD_VALIDATORS["jira_issue_ref"] = _validator_jira_issue_ref
FIELD_VALIDATORS["jira_update_payload"] = _validator_jira_update_payload
FIELD_VALIDATORS["named_or_payload"] = _validator_named_or_payload
FIELD_VALIDATORS["zendesk_ticket_body"] = _validator_zendesk_ticket_body
FIELD_VALIDATORS["salesforce_task_subject"] = _validator_salesforce_task_subject
FIELD_VALIDATORS["asana_task_update"] = _validator_asana_task_update


def _validator_object_payload(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    for key in field.arg_keys:
        if _dict_has_content(args.get(key)):
            return True
    return False


def _validator_tags_payload(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    tags = args.get("tags")
    if isinstance(tags, list) and tags:
        return True
    return bool(str(tags or "").strip())


def _validator_list_payload(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    for key in field.arg_keys:
        value = args.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def _validator_list_or_object_payload(args: dict[str, Any], field: WorkflowFieldSpec) -> bool:
    for key in field.arg_keys:
        value = args.get(key)
        if isinstance(value, list) and value:
            return True
        if _dict_has_content(value):
            return True
    return False


FIELD_VALIDATORS["object_payload"] = _validator_object_payload
FIELD_VALIDATORS["tags_payload"] = _validator_tags_payload
FIELD_VALIDATORS["list_payload"] = _validator_list_payload
FIELD_VALIDATORS["list_or_object_payload"] = _validator_list_or_object_payload


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
