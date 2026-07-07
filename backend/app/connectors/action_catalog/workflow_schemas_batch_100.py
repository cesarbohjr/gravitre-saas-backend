"""Priority write-action workflow schemas — batch 4 of pending_schema shrink (25 actions)."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

BATCH_100_ACTION_KEYS: tuple[str, ...] = (
    "microsoft365.calendar.events.create",
    "microsoft365.files.upload",
    "microsoft365.teams.meetings.create",
    "microsoft365.teams.messages.send",
    "quickbooks.customers.create",
    "quickbooks.invoices.create",
    "quickbooks.payments.create",
    "xero.contacts.create",
    "xero.invoices.create",
    "xero.payments.create",
    "segment.track",
    "segment.identify",
    "segment.group",
    "marketo.leads.create",
    "marketo.leads.update",
    "marketo.campaigns.schedule",
    "github.pulls.request_reviewer",
    "gorgias.tickets.create",
    "gorgias.tickets.reply",
    "gorgias.macros.apply",
    "greenhouse.candidates.create",
    "pagerduty.incidents.acknowledge",
    "pagerduty.incidents.resolve",
    "netsuite.salesorders.create",
    "motion.tasks.create",
)


def _req(label: str, *keys: str, validator: str | None = None) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, validator=validator)


def _opt(label: str, *keys: str) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys)


WORKFLOW_SCHEMAS_BATCH_100: dict[str, ActionWorkflowSchema] = {
    "microsoft365.calendar.events.create": ActionWorkflowSchema(
        intent_label="Create Microsoft 365 calendar event",
        required_fields=(
            _req("event title", "subject", "title"),
            _req("start time", "start", "start_datetime"),
            _req("end time", "end", "end_datetime"),
        ),
        optional_fields=(_opt("Body", "body"),),
    ),
    "microsoft365.files.upload": ActionWorkflowSchema(
        intent_label="Upload Microsoft 365 file",
        required_fields=(
            _req("filename", "filename", "name"),
            _req("file content", "content", validator="named_or_payload"),
        ),
        optional_fields=(_opt("Parent folder", "parent_id"),),
    ),
    "microsoft365.teams.meetings.create": ActionWorkflowSchema(
        intent_label="Create Microsoft Teams meeting",
        required_fields=(
            _req("meeting title", "subject", "title"),
            _req("start time", "start", "start_datetime"),
            _req("end time", "end", "end_datetime"),
        ),
    ),
    "microsoft365.teams.messages.send": ActionWorkflowSchema(
        intent_label="Send Microsoft Teams channel message",
        required_fields=(
            _req("team id", "team_id"),
            _req("channel id", "channel_id"),
            _req("message", "content", "text"),
        ),
    ),
    "quickbooks.customers.create": ActionWorkflowSchema(
        intent_label="Create QuickBooks customer",
        required_fields=(_req("customer details", "name", "payload", "fields", validator="named_or_payload"),),
    ),
    "quickbooks.invoices.create": ActionWorkflowSchema(
        intent_label="Create QuickBooks invoice",
        required_fields=(_req("invoice details", "customer", "payload", "fields", validator="named_or_payload"),),
    ),
    "quickbooks.payments.create": ActionWorkflowSchema(
        intent_label="Record QuickBooks payment",
        required_fields=(_req("payment details", "amount", "payload", "fields", validator="named_or_payload"),),
    ),
    "xero.contacts.create": ActionWorkflowSchema(
        intent_label="Create Xero contact",
        required_fields=(_req("contact details", "name", "payload", "fields", validator="named_or_payload"),),
    ),
    "xero.invoices.create": ActionWorkflowSchema(
        intent_label="Create Xero invoice",
        required_fields=(_req("invoice details", "contact", "payload", "fields", validator="named_or_payload"),),
    ),
    "xero.payments.create": ActionWorkflowSchema(
        intent_label="Create Xero payment",
        required_fields=(_req("payment details", "amount", "payload", "fields", validator="named_or_payload"),),
    ),
    "segment.track": ActionWorkflowSchema(
        intent_label="Track Segment event",
        required_fields=(_req("event name", "event", "event_name"),),
        optional_fields=(_opt("User id", "user_id", "userId"), _opt("Properties", "properties"),),
    ),
    "segment.identify": ActionWorkflowSchema(
        intent_label="Identify Segment user",
        required_fields=(_req("user id", "user_id", "userId"),),
        optional_fields=(_opt("Traits", "traits"),),
    ),
    "segment.group": ActionWorkflowSchema(
        intent_label="Group Segment user",
        required_fields=(
            _req("user id", "user_id", "userId"),
            _req("group id", "group_id", "groupId"),
        ),
        optional_fields=(_opt("Traits", "traits"),),
    ),
    "marketo.leads.create": ActionWorkflowSchema(
        intent_label="Create Marketo lead",
        required_fields=(_req("lead fields", "email", "payload", "fields", validator="named_or_payload"),),
    ),
    "marketo.leads.update": ActionWorkflowSchema(
        intent_label="Update Marketo lead",
        required_fields=(
            _req("lead id", "lead_id", "email"),
            _req("update fields", "fields", "payload", validator="object_payload"),
        ),
    ),
    "marketo.campaigns.schedule": ActionWorkflowSchema(
        intent_label="Schedule Marketo campaign",
        required_fields=(
            _req("campaign id", "campaign_id"),
            _req("schedule details", "run_at", "payload", validator="named_or_payload"),
        ),
    ),
    "github.pulls.request_reviewer": ActionWorkflowSchema(
        intent_label="Request GitHub pull request reviewer",
        required_fields=(
            _req("pull request", "pull_number", "number", "pull_request_number"),
            _req("reviewer", "reviewer", "reviewers", validator="named_or_payload"),
        ),
        optional_fields=(_opt("Repository", "repo", "repository"),),
    ),
    "gorgias.tickets.create": ActionWorkflowSchema(
        intent_label="Create Gorgias ticket",
        required_fields=(
            _req("subject", "subject"),
            _req("message body", "body", "message", validator="zendesk_ticket_body"),
        ),
    ),
    "gorgias.tickets.reply": ActionWorkflowSchema(
        intent_label="Reply to Gorgias ticket",
        required_fields=(
            _req("ticket id", "ticket_id"),
            _req("reply body", "body", "message", validator="zendesk_ticket_body"),
        ),
    ),
    "gorgias.macros.apply": ActionWorkflowSchema(
        intent_label="Apply Gorgias macro",
        required_fields=(
            _req("ticket id", "ticket_id"),
            _req("macro id", "macro_id"),
        ),
    ),
    "greenhouse.candidates.create": ActionWorkflowSchema(
        intent_label="Create Greenhouse candidate",
        required_fields=(_req("candidate details", "first_name", "email", "payload", validator="named_or_payload"),),
    ),
    "pagerduty.incidents.acknowledge": ActionWorkflowSchema(
        intent_label="Acknowledge PagerDuty incident",
        required_fields=(_req("incident id", "incident_id", "id"),),
    ),
    "pagerduty.incidents.resolve": ActionWorkflowSchema(
        intent_label="Resolve PagerDuty incident",
        required_fields=(_req("incident id", "incident_id", "id"),),
    ),
    "netsuite.salesorders.create": ActionWorkflowSchema(
        intent_label="Create NetSuite sales order",
        required_fields=(_req("order payload", "payload", "fields", validator="object_payload"),),
    ),
    "motion.tasks.create": ActionWorkflowSchema(
        intent_label="Create Motion task",
        required_fields=(_req("task details", "name", "title", "payload", validator="named_or_payload"),),
    ),
}
