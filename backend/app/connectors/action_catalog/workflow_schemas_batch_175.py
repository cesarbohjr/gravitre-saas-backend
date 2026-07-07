"""Priority write-action workflow schemas — batch 7 of pending_schema shrink (18 actions)."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

BATCH_175_ACTION_KEYS: tuple[str, ...] = (
    "figma.dev_resources.create",
    "gusto.employees.create",
    "gusto.payrolls.run",
    "hootsuite.messages.schedule",
    "hootsuite.messages.update",
    "microsoft_teams.meetings.create",
    "microsoft_teams.messages.send",
    "plaid.link.token.create",
    "plaid.public_token.exchange",
    "real_estate.handoff.brief",
    "real_estate.listing.publish",
    "real_estate.mls.note",
    "semrush.position_tracking.add",
    "semrush.projects.create",
    "stackadapt.campaigns.create",
    "stackadapt.campaigns.update",
    "workday.jobs.update",
    "workday.timeoff.request",
)


def _req(label: str, *keys: str, validator: str | None = None) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, validator=validator)


def _opt(label: str, *keys: str) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys)


WORKFLOW_SCHEMAS_BATCH_175: dict[str, ActionWorkflowSchema] = {
    "figma.dev_resources.create": ActionWorkflowSchema(
        intent_label="Create Figma dev resource",
        required_fields=(
            _req("file key", "file_key", "fileKey"),
            _req("dev resource payload", "payload", "properties", validator="object_payload"),
        ),
    ),
    "gusto.employees.create": ActionWorkflowSchema(
        intent_label="Create Gusto employee",
        required_fields=(
            _req("first name", "firstname", "first_name"),
            _req("last name", "lastname", "last_name"),
            _req("email", "email"),
        ),
        optional_fields=(_opt("Employee fields", "properties", "payload"),),
    ),
    "gusto.payrolls.run": ActionWorkflowSchema(
        intent_label="Run Gusto payroll",
        required_fields=(_req("payroll id", "payroll_id", "id"),),
        optional_fields=(_opt("Parameters", "parameters"),),
    ),
    "hootsuite.messages.schedule": ActionWorkflowSchema(
        intent_label="Schedule Hootsuite message",
        required_fields=(
            _req("message text", "text", "message", "body"),
            _req("scheduled time", "scheduled_at", "scheduledTime"),
        ),
        optional_fields=(_opt("Social profiles", "profile_ids", "social_profiles"),),
    ),
    "hootsuite.messages.update": ActionWorkflowSchema(
        intent_label="Update Hootsuite message",
        required_fields=(
            _req("message id", "message_id", "id"),
            _req("update properties", "properties", "payload", "text", validator="named_or_payload"),
        ),
        optional_fields=(_opt("Scheduled time", "scheduled_at", "scheduledTime"),),
    ),
    "microsoft_teams.meetings.create": ActionWorkflowSchema(
        intent_label="Create Microsoft Teams meeting",
        required_fields=(
            _req("meeting subject", "subject", "title"),
            _req("start time", "start", "start_datetime"),
            _req("end time", "end", "end_datetime"),
        ),
    ),
    "microsoft_teams.messages.send": ActionWorkflowSchema(
        intent_label="Send Microsoft Teams channel message",
        required_fields=(
            _req("team id", "team_id"),
            _req("channel id", "channel_id"),
            _req("message content", "content", "text", "message", "body", validator="named_or_payload"),
        ),
    ),
    "plaid.link.token.create": ActionWorkflowSchema(
        intent_label="Create Plaid link token",
        required_fields=(
            _req("client name", "client_name"),
            _req("user id", "user_id", "user"),
            _req("products list", "products", "payload", validator="named_or_payload"),
        ),
        optional_fields=(_opt("Language", "language"), _opt("Country codes", "country_codes"),),
    ),
    "plaid.public_token.exchange": ActionWorkflowSchema(
        intent_label="Exchange Plaid public token",
        required_fields=(_req("public token", "public_token"),),
    ),
    "real_estate.handoff.brief": ActionWorkflowSchema(
        intent_label="Create real estate handoff brief",
        required_fields=(
            _req("buyer name", "buyer_name", "buyerName"),
            _req("property address", "property_address", "propertyAddress"),
        ),
    ),
    "real_estate.listing.publish": ActionWorkflowSchema(
        intent_label="Publish real estate listing",
        required_fields=(_req("listing id", "listing_id", "id"),),
    ),
    "real_estate.mls.note": ActionWorkflowSchema(
        intent_label="Create real estate MLS note",
        required_fields=(
            _req("property address", "property_address", "propertyAddress"),
            _req("list price", "list_price", "listPrice"),
        ),
    ),
    "semrush.position_tracking.add": ActionWorkflowSchema(
        intent_label="Add Semrush position tracking keywords",
        required_fields=(
            _req("project id", "project_id", "project"),
            _req("keywords list", "keywords", "payload", validator="list_or_object_payload"),
        ),
    ),
    "semrush.projects.create": ActionWorkflowSchema(
        intent_label="Create Semrush project",
        required_fields=(_req("project name", "name", "title", "properties", validator="named_or_payload"),),
        optional_fields=(_opt("Project URL", "project_url", "url"),),
    ),
    "stackadapt.campaigns.create": ActionWorkflowSchema(
        intent_label="Create StackAdapt campaign",
        required_fields=(
            _req("campaign name", "name", "title"),
            _req("campaign budget", "budget", "payload", validator="named_or_payload"),
        ),
        optional_fields=(_opt("Campaign type", "campaign_type"),),
    ),
    "stackadapt.campaigns.update": ActionWorkflowSchema(
        intent_label="Update StackAdapt campaign",
        required_fields=(
            _req("campaign id", "campaign_id"),
            _req("update fields", "properties", "payload", validator="object_payload"),
        ),
    ),
    "workday.jobs.update": ActionWorkflowSchema(
        intent_label="Update Workday job",
        required_fields=(
            _req("worker id", "worker_id", "id"),
            _req("update fields", "properties", "payload", validator="object_payload"),
        ),
        optional_fields=(_opt("Job profile id", "job_profile_id"),),
    ),
    "workday.timeoff.request": ActionWorkflowSchema(
        intent_label="Request Workday time off",
        required_fields=(
            _req("worker id", "worker_id", "id"),
            _req("start date", "start_date", "start"),
            _req("end date", "end_date", "end"),
        ),
        optional_fields=(_opt("Time off type", "time_off_type_id", "time_off_type"),),
    ),
}
