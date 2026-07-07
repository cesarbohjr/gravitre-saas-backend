"""Priority write-action workflow schemas — batch 6 of pending_schema shrink (25 actions)."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

BATCH_150_ACTION_KEYS: tuple[str, ...] = (
    "absorb_lms.courses.create",
    "absorb_lms.enrollments.create",
    "adp.profile.update",
    "adp.timecards.submit",
    "asana.stories.create",
    "aws_s3.objects.delete",
    "bamboohr.employees.create",
    "bamboohr.timeoff.requests.create",
    "canva.designs.create",
    "canva.exports.create",
    "clay.enrichments.request",
    "clay.leads.push",
    "clio.conflict.checklist",
    "clio.intake.tasks",
    "clio.matters.create",
    "clio.tasks.create",
    "confluence.labels.add",
    "constant_contact.campaigns.create",
    "constant_contact.contacts.create",
    "constant_contact.contacts.update",
    "email.send",
    "engagebay.contacts.create",
    "engagebay.contacts.update",
    "fhir.prior_auth.checklist",
    "figma.comments.create",
)


def _req(label: str, *keys: str, validator: str | None = None) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, validator=validator)


def _opt(label: str, *keys: str) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys)


WORKFLOW_SCHEMAS_BATCH_150: dict[str, ActionWorkflowSchema] = {
    "absorb_lms.courses.create": ActionWorkflowSchema(
        intent_label="Create Absorb LMS course",
        required_fields=(
            _req("course name", "name", "title", "payload", validator="named_or_payload"),
        ),
        optional_fields=(_opt("Description", "description"),),
    ),
    "absorb_lms.enrollments.create": ActionWorkflowSchema(
        intent_label="Create Absorb LMS enrollment",
        required_fields=(
            _req("course id", "course_id", "course"),
            _req("user id", "user_id", "email", "learner_id"),
        ),
    ),
    "adp.profile.update": ActionWorkflowSchema(
        intent_label="Update ADP worker profile",
        required_fields=(
            _req("profile id", "profile_id", "worker_id"),
            _req("update fields", "properties", "payload", validator="object_payload"),
        ),
    ),
    "adp.timecards.submit": ActionWorkflowSchema(
        intent_label="Submit ADP timecard",
        required_fields=(_req("timecard id", "timecard_id", "id"),),
        optional_fields=(_opt("Comment", "comment"), _opt("Properties", "properties", "payload"),),
    ),
    "asana.stories.create": ActionWorkflowSchema(
        intent_label="Add Asana task comment",
        required_fields=(
            _req("task id", "task_id", "taskId"),
            _req("comment body", "text", "body", "comment", validator="named_or_payload"),
        ),
    ),
    "aws_s3.objects.delete": ActionWorkflowSchema(
        intent_label="Delete S3 object",
        required_fields=(
            _req("bucket", "bucket"),
            _req("object key", "key", "object_key", "object_id"),
        ),
    ),
    "bamboohr.employees.create": ActionWorkflowSchema(
        intent_label="Create BambooHR employee",
        required_fields=(
            _req("first name", "firstname", "first_name"),
            _req("last name", "lastname", "last_name"),
            _req("email", "email"),
        ),
        optional_fields=(_opt("Employee fields", "properties", "payload"),),
    ),
    "bamboohr.timeoff.requests.create": ActionWorkflowSchema(
        intent_label="Create BambooHR time off request",
        required_fields=(
            _req("employee id", "employee_id"),
            _req("start date", "start_date", "start"),
            _req("end date", "end_date", "end"),
        ),
        optional_fields=(
            _opt("Time off type", "time_off_type", "type_id"),
            _opt("Comment", "comment", "reason"),
        ),
    ),
    "canva.designs.create": ActionWorkflowSchema(
        intent_label="Create Canva design",
        required_fields=(_req("design payload", "payload", "properties", validator="object_payload"),),
        optional_fields=(
            _opt("Design type", "design_type"),
            _opt("Asset id", "asset_id"),
            _opt("Title", "title"),
        ),
    ),
    "canva.exports.create": ActionWorkflowSchema(
        intent_label="Export Canva design",
        required_fields=(
            _req("design id", "design_id", "designId"),
            _req("export format", "format"),
        ),
    ),
    "clay.enrichments.request": ActionWorkflowSchema(
        intent_label="Request Clay enrichment",
        required_fields=(
            _req("enrichment records", "records", "record", validator="list_or_object_payload"),
        ),
        optional_fields=(_opt("Table id", "table_id", "tableId"),),
    ),
    "clay.leads.push": ActionWorkflowSchema(
        intent_label="Push leads to Clay",
        required_fields=(
            _req("lead records", "records", "record", "payload", validator="list_or_object_payload"),
        ),
        optional_fields=(
            _opt("Table id", "table_id", "tableId"),
            _opt("Webhook url", "webhook_url", "webhookUrl"),
        ),
    ),
    "clio.conflict.checklist": ActionWorkflowSchema(
        intent_label="Run Clio conflict checklist",
        required_fields=(_req("prospect name", "prospect_name", "prospectName"),),
        optional_fields=(_opt("Matter type", "matter_type", "matterType"),),
    ),
    "clio.intake.tasks": ActionWorkflowSchema(
        intent_label="Create Clio intake tasks",
        required_fields=(_req("matter name", "matter_name", "matterName"),),
    ),
    "clio.matters.create": ActionWorkflowSchema(
        intent_label="Create Clio matter",
        required_fields=(
            _req("client id", "client_id", "client"),
            _req("matter description", "description", "name"),
        ),
        optional_fields=(_opt("Practice area", "practice_area"),),
    ),
    "clio.tasks.create": ActionWorkflowSchema(
        intent_label="Create Clio task",
        required_fields=(
            _req("subject", "subject", "name"),
            _req("matter id", "matter_id", "matter"),
        ),
        optional_fields=(_opt("Description", "description"), _opt("Due date", "due_at", "due_date"),),
    ),
    "confluence.labels.add": ActionWorkflowSchema(
        intent_label="Add Confluence page labels",
        required_fields=(
            _req("page id", "page_id", "id"),
            _req("labels list", "labels", "payload", validator="list_or_object_payload"),
        ),
    ),
    "constant_contact.campaigns.create": ActionWorkflowSchema(
        intent_label="Create Constant Contact campaign",
        required_fields=(
            _req("campaign name", "name"),
            _req(
                "campaign activities",
                "email_campaign_activities",
                "activities",
                "payload",
                validator="named_or_payload",
            ),
        ),
    ),
    "constant_contact.contacts.create": ActionWorkflowSchema(
        intent_label="Create Constant Contact contact",
        required_fields=(_req("email", "email", "payload", validator="named_or_payload"),),
        optional_fields=(
            _opt("First name", "firstname", "first_name"),
            _opt("Last name", "lastname", "last_name"),
        ),
    ),
    "constant_contact.contacts.update": ActionWorkflowSchema(
        intent_label="Update Constant Contact contact",
        required_fields=(
            _req("contact id", "contact_id"),
            _req("update fields", "properties", "payload", validator="object_payload"),
        ),
    ),
    "email.send": ActionWorkflowSchema(
        intent_label="Send email",
        required_fields=(
            _req("recipient", "to"),
            _req("subject", "subject"),
            _req("body", "body", "text"),
        ),
        optional_fields=(_opt("Content type", "content_type"),),
    ),
    "engagebay.contacts.create": ActionWorkflowSchema(
        intent_label="Create EngageBay contact",
        required_fields=(_req("email", "email"),),
        optional_fields=(
            _opt("First name", "firstname", "first_name"),
            _opt("Last name", "lastname", "last_name"),
            _opt("Properties", "properties", "payload"),
        ),
    ),
    "engagebay.contacts.update": ActionWorkflowSchema(
        intent_label="Update EngageBay contact",
        required_fields=(
            _req("contact id", "contact_id"),
            _req("update fields", "properties", "payload", validator="object_payload"),
        ),
    ),
    "fhir.prior_auth.checklist": ActionWorkflowSchema(
        intent_label="Generate FHIR prior auth checklist",
        required_fields=(_req("patient id", "patient_id", "patientId"),),
        optional_fields=(
            _opt("Referral reason", "referral_reason", "referralReason"),
            _opt("Payer", "payer"),
        ),
    ),
    "figma.comments.create": ActionWorkflowSchema(
        intent_label="Create Figma comment",
        required_fields=(
            _req("file key", "file_key", "fileKey"),
            _req("comment message", "message", "text", "body", validator="named_or_payload"),
        ),
    ),
}
