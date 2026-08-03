"""Priority write-action workflow schemas — batch 2 of pending_schema shrink (25 actions)."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

BATCH_50_ACTION_KEYS: tuple[str, ...] = (
    "hubspot.deals.delete",
    "hubspot.contacts.delete",
    "hubspot.notes.delete",
    "slack.conversations.create",
    "slack.chat.update",
    "stripe.customers.create",
    "stripe.invoices.create",
    "sendgrid.mail.send",
    "sendgrid.contacts.upsert",
    "outlook.messages.send",  # aliased → microsoft365.mail.send (STA-337)
    "microsoft365.mail.send",
    "salesforce.opportunities.create",
    "salesforce.leads.update",
    "salesforce.accounts.create",
    "pipedrive.deals.update",
    "pipedrive.persons.update",
    "freshdesk.tickets.create",
    "github.issues.comment",
    "google_docs.documents.create",
    "google_calendar.events.update",
    "twilio.messages.create",
    "webhook.post",
    "zendesk.tickets.close",
    "zendesk.tickets.add_tags",
)


def _req(label: str, *keys: str, validator: str | None = None) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, validator=validator)


def _opt(label: str, *keys: str) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys)


WORKFLOW_SCHEMAS_BATCH_50: dict[str, ActionWorkflowSchema] = {
    "hubspot.deals.delete": ActionWorkflowSchema(
        intent_label="Delete HubSpot deal",
        required_fields=(_req("deal id", "deal_id"),),
    ),
    "hubspot.contacts.delete": ActionWorkflowSchema(
        intent_label="Delete HubSpot contact",
        required_fields=(_req("contact id", "contact_id"),),
    ),
    "hubspot.notes.delete": ActionWorkflowSchema(
        intent_label="Delete HubSpot note",
        required_fields=(_req("note id", "note_id"),),
    ),
    "slack.conversations.create": ActionWorkflowSchema(
        intent_label="Create Slack channel",
        required_fields=(_req("channel name", "name"),),
        optional_fields=(_opt("Private channel", "is_private"),),
    ),
    "slack.chat.update": ActionWorkflowSchema(
        intent_label="Update Slack message",
        required_fields=(
            _req("channel", "channel"),
            _req("message timestamp", "ts"),
            _req("updated text", "text", "message"),
        ),
    ),
    "stripe.customers.create": ActionWorkflowSchema(
        intent_label="Create Stripe customer",
        required_fields=(
            _req("email or customer details", "email", "name", "payload", validator="named_or_payload"),
        ),
    ),
    "stripe.invoices.create": ActionWorkflowSchema(
        intent_label="Create Stripe invoice",
        required_fields=(
            _req("customer", "customer", "customer_id"),
            _req("invoice details", "payload", "lines", validator="named_or_payload"),
        ),
    ),
    "sendgrid.mail.send": ActionWorkflowSchema(
        intent_label="Send SendGrid email",
        required_fields=(
            _req("recipient", "to"),
            _req("subject", "subject"),
            _req("body", "body", "html", "text"),
        ),
    ),
    "sendgrid.contacts.upsert": ActionWorkflowSchema(
        intent_label="Upsert SendGrid contact",
        required_fields=(_req("email", "email"),),
        optional_fields=(_opt("Contact fields", "payload", "properties"),),
    ),
    "outlook.messages.send": ActionWorkflowSchema(
        intent_label="Send Outlook message (via Microsoft 365)",
        required_fields=(
            _req("recipient", "to"),
            _req("subject", "subject"),
            _req("body", "body"),
        ),
    ),
    "microsoft365.mail.send": ActionWorkflowSchema(
        intent_label="Send Microsoft 365 email",
        required_fields=(
            _req("recipient", "to"),
            _req("subject", "subject"),
            _req("body", "body"),
        ),
    ),
    "salesforce.opportunities.create": ActionWorkflowSchema(
        intent_label="Create Salesforce opportunity",
        required_fields=(_req("opportunity fields", "fields", "payload", validator="named_or_payload"),),
    ),
    "salesforce.leads.update": ActionWorkflowSchema(
        intent_label="Update Salesforce lead",
        required_fields=(
            _req("lead id", "lead_id"),
            _req("update fields", "fields", validator="object_payload"),
        ),
    ),
    "salesforce.accounts.create": ActionWorkflowSchema(
        intent_label="Create Salesforce account",
        required_fields=(_req("account fields", "fields", "payload", validator="named_or_payload"),),
    ),
    "pipedrive.deals.update": ActionWorkflowSchema(
        intent_label="Update Pipedrive deal",
        required_fields=(
            _req("deal id", "deal_id"),
            _req("update payload", "payload", "properties", validator="object_payload"),
        ),
    ),
    "pipedrive.persons.update": ActionWorkflowSchema(
        intent_label="Update Pipedrive person",
        required_fields=(
            _req("person id", "person_id"),
            _req("update payload", "payload", "properties", validator="object_payload"),
        ),
    ),
    "freshdesk.tickets.create": ActionWorkflowSchema(
        intent_label="Create Freshdesk ticket",
        required_fields=(
            _req("subject", "subject"),
            _req("description", "description", "body", validator="zendesk_ticket_body"),
        ),
    ),
    "github.issues.comment": ActionWorkflowSchema(
        intent_label="Comment on GitHub issue",
        required_fields=(
            _req("issue number", "issue_number", "number"),
            _req("comment body", "body", "comment"),
        ),
    ),
    "google_docs.documents.create": ActionWorkflowSchema(
        intent_label="Create Google Doc",
        required_fields=(_req("document title", "title", "name"),),
    ),
    "google_calendar.events.update": ActionWorkflowSchema(
        intent_label="Update Google Calendar event",
        required_fields=(
            _req("event id", "event_id", "id"),
            _req("update fields", "summary", "start", "payload", validator="named_or_payload"),
        ),
    ),
    "twilio.messages.create": ActionWorkflowSchema(
        intent_label="Send Twilio SMS",
        required_fields=(
            _req("recipient", "to", "phone"),
            _req("message body", "body", "message"),
        ),
    ),
    "webhook.post": ActionWorkflowSchema(
        intent_label="POST webhook payload",
        required_fields=(_req("payload", "payload", validator="object_payload"),),
        optional_fields=(_opt("Path", "path"),),
    ),
    "zendesk.tickets.close": ActionWorkflowSchema(
        intent_label="Close Zendesk ticket",
        required_fields=(_req("ticket id", "ticket_id"),),
        optional_fields=(_opt("Closing comment", "comment"),),
    ),
    "zendesk.tickets.add_tags": ActionWorkflowSchema(
        intent_label="Add Zendesk ticket tags",
        required_fields=(
            _req("ticket id", "ticket_id"),
            _req("tags", "tags", validator="tags_payload"),
        ),
    ),
}
