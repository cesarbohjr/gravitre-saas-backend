"""Priority write-action workflow schemas — batch 3 of pending_schema shrink (25 actions)."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

BATCH_75_ACTION_KEYS: tuple[str, ...] = (
    "freshdesk.tickets.update",
    "freshdesk.notes.create",
    "google_calendar.events.delete",
    "google_docs.documents.batch_update",
    "google_drive.files.update",
    "google_drive.permissions.create",
    "google_sheets.spreadsheets.create",
    "google_sheets.values.append",
    "google_sheets.values.update",
    "gmail.drafts.create",
    "gmail.labels.create",
    "stripe.refunds.create",
    "twilio.calls.create",
    "mailchimp.campaigns.create",
    "mailchimp.members.add",
    "mailchimp.tags.add",
    "clickup.tasks.update",
    "clickup.comments.create",
    "confluence.pages.create",
    "confluence.pages.update",
    "notion.blocks.append",
    "intercom.tickets.create",
    "intercom.conversations.reply",
    "airtable.records.create",
    "airtable.records.update",
)


def _req(label: str, *keys: str, validator: str | None = None) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, validator=validator)


def _opt(label: str, *keys: str) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys)


WORKFLOW_SCHEMAS_BATCH_75: dict[str, ActionWorkflowSchema] = {
    "freshdesk.tickets.update": ActionWorkflowSchema(
        intent_label="Update Freshdesk ticket",
        required_fields=(
            _req("ticket id", "ticket_id"),
            _req("update fields", "subject", "status", "payload", "properties", validator="named_or_payload"),
        ),
    ),
    "freshdesk.notes.create": ActionWorkflowSchema(
        intent_label="Add Freshdesk ticket note",
        required_fields=(
            _req("ticket id", "ticket_id"),
            _req("note body", "body", "note", "description"),
        ),
    ),
    "google_calendar.events.delete": ActionWorkflowSchema(
        intent_label="Delete Google Calendar event",
        required_fields=(_req("event id", "event_id", "id"),),
        optional_fields=(_opt("Calendar", "calendar_id"),),
    ),
    "google_docs.documents.batch_update": ActionWorkflowSchema(
        intent_label="Batch update Google Doc",
        required_fields=(
            _req("document id", "document_id"),
            _req("update requests", "requests", "payload", validator="list_or_object_payload"),
        ),
    ),
    "google_drive.files.update": ActionWorkflowSchema(
        intent_label="Update Google Drive file",
        required_fields=(
            _req("file id", "file_id"),
            _req("update fields", "name", "description", "payload", validator="named_or_payload"),
        ),
    ),
    "google_drive.permissions.create": ActionWorkflowSchema(
        intent_label="Share Google Drive file",
        required_fields=(
            _req("file id", "file_id"),
            _req("role or recipient", "role", "email", validator="named_or_payload"),
        ),
    ),
    "google_sheets.spreadsheets.create": ActionWorkflowSchema(
        intent_label="Create Google Sheet",
        required_fields=(_req("spreadsheet title", "title", "name"),),
    ),
    "google_sheets.values.append": ActionWorkflowSchema(
        intent_label="Append Google Sheets values",
        required_fields=(
            _req("spreadsheet id", "spreadsheet_id"),
            _req("range", "range"),
            _req("values", "values", validator="list_payload"),
        ),
    ),
    "google_sheets.values.update": ActionWorkflowSchema(
        intent_label="Update Google Sheets values",
        required_fields=(
            _req("spreadsheet id", "spreadsheet_id"),
            _req("range", "range"),
            _req("values", "values", validator="list_payload"),
        ),
    ),
    "gmail.drafts.create": ActionWorkflowSchema(
        intent_label="Create Gmail draft",
        required_fields=(
            _req("recipient", "to"),
            _req("subject", "subject"),
            _req("body", "body"),
        ),
    ),
    "gmail.labels.create": ActionWorkflowSchema(
        intent_label="Create Gmail label",
        required_fields=(_req("label name", "name"),),
    ),
    "stripe.refunds.create": ActionWorkflowSchema(
        intent_label="Create Stripe refund",
        required_fields=(
            _req("charge or payment intent", "charge", "charge_id", "payment_intent", validator="named_or_payload"),
        ),
        optional_fields=(_opt("Amount", "amount"),),
    ),
    "twilio.calls.create": ActionWorkflowSchema(
        intent_label="Place Twilio call",
        required_fields=(
            _req("recipient", "to", "phone"),
            _req("call script URL", "url", "twiml", validator="named_or_payload"),
        ),
    ),
    "mailchimp.campaigns.create": ActionWorkflowSchema(
        intent_label="Create Mailchimp campaign",
        required_fields=(
            _req("campaign details", "type", "subject", "list_id", "payload", validator="named_or_payload"),
        ),
    ),
    "mailchimp.members.add": ActionWorkflowSchema(
        intent_label="Add Mailchimp list member",
        required_fields=(
            _req("list id", "list_id"),
            _req("email", "email"),
        ),
    ),
    "mailchimp.tags.add": ActionWorkflowSchema(
        intent_label="Add Mailchimp member tags",
        required_fields=(
            _req("list id", "list_id"),
            _req("email", "email"),
            _req("tags", "tags", validator="tags_payload"),
        ),
    ),
    "clickup.tasks.update": ActionWorkflowSchema(
        intent_label="Update ClickUp task",
        required_fields=(
            _req("task id", "task_id", "taskId"),
            _req("update payload", "payload", "properties", validator="object_payload"),
        ),
    ),
    "clickup.comments.create": ActionWorkflowSchema(
        intent_label="Comment on ClickUp task",
        required_fields=(
            _req("task id", "task_id", "taskId"),
            _req("comment text", "comment_text", "comment", "body"),
        ),
    ),
    "confluence.pages.create": ActionWorkflowSchema(
        intent_label="Create Confluence page",
        required_fields=(
            _req("space", "space", "space_key"),
            _req("page title", "title"),
        ),
        optional_fields=(_opt("Body", "body", "content"),),
    ),
    "confluence.pages.update": ActionWorkflowSchema(
        intent_label="Update Confluence page",
        required_fields=(
            _req("page id", "page_id"),
            _req("update payload", "title", "body", "payload", validator="named_or_payload"),
        ),
    ),
    "notion.blocks.append": ActionWorkflowSchema(
        intent_label="Append Notion blocks",
        required_fields=(
            _req("block or page id", "block_id", "page_id", "parent_id"),
            _req("blocks", "children", "blocks", "payload", validator="list_or_object_payload"),
        ),
    ),
    "intercom.tickets.create": ActionWorkflowSchema(
        intent_label="Create Intercom ticket",
        required_fields=(_req("ticket details", "title", "description", "payload", validator="named_or_payload"),),
    ),
    "intercom.conversations.reply": ActionWorkflowSchema(
        intent_label="Reply to Intercom conversation",
        required_fields=(
            _req("conversation id", "conversation_id", "conversationId"),
            _req("reply body", "body", "message", "payload", validator="named_or_payload"),
        ),
    ),
    "airtable.records.create": ActionWorkflowSchema(
        intent_label="Create Airtable records",
        required_fields=(
            _req("base id", "base_id", "base"),
            _req("table", "table", "table_id", "table_name"),
            _req("record fields", "fields", "records", "payload", validator="object_payload"),
        ),
    ),
    "airtable.records.update": ActionWorkflowSchema(
        intent_label="Update Airtable records",
        required_fields=(
            _req("base id", "base_id", "base"),
            _req("table", "table", "table_id", "table_name"),
            _req("record id", "record_id"),
            _req("update fields", "fields", "payload", validator="object_payload"),
        ),
    ),
}
