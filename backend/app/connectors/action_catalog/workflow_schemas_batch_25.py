"""Priority write-action workflow schemas — batch 1 of pending_schema shrink (25 actions)."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

BATCH_25_ACTION_KEYS: tuple[str, ...] = (
    "hubspot.deals.create",
    "hubspot.deals.update",
    "hubspot.contacts.update",
    "hubspot.notes.create",
    "jira.issues.create",
    "jira.issues.update",
    "jira.issues.comment",
    "gmail.messages.send",
    "google_calendar.events.create",
    "google_drive.files.create",
    "monday.items.create",
    "monday.items.update",
    "notion.pages.create",
    "notion.pages.update",
    "zendesk.tickets.create",
    "zendesk.tickets.update",
    "salesforce.leads.create",
    "salesforce.tasks.create",
    "apollo.contacts.create",
    "github.issues.create",
    "github.pulls.create",
    "github.issues.update",
    "clickup.tasks.create",
    "pipedrive.deals.create",
    "pipedrive.persons.create",
    "intercom.contacts.create",
    "asana.tasks.update",
)


def _req(
    label: str,
    *keys: str,
    validator: str | None = None,
    sensitive: bool = False,
) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, validator=validator, sensitive=sensitive)


def _opt(label: str, *keys: str, sensitive: bool = False) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, sensitive=sensitive)


WORKFLOW_SCHEMAS_BATCH_25: dict[str, ActionWorkflowSchema] = {
    "hubspot.deals.create": ActionWorkflowSchema(
        intent_label="Create HubSpot deal",
        required_fields=(
            _req("deal name", "dealname", "properties", validator="hubspot_deal_create"),
        ),
        optional_fields=(_opt("Amount", "amount"),),
    ),
    "hubspot.deals.update": ActionWorkflowSchema(
        intent_label="Update HubSpot deal",
        required_fields=(
            _req("deal id", "deal_id"),
            _req("update properties", "properties", validator="hubspot_properties_payload"),
        ),
    ),
    "hubspot.contacts.update": ActionWorkflowSchema(
        intent_label="Update HubSpot contact",
        required_fields=(
            _req("contact id", "contact_id"),
            _req("update properties", "properties", validator="hubspot_properties_payload"),
        ),
    ),
    "hubspot.notes.create": ActionWorkflowSchema(
        intent_label="Create HubSpot note",
        required_fields=(_req("note body", "body"),),
        optional_fields=(
            _opt("Contact id", "contact_id"),
            _opt("Deal id", "deal_id"),
            _opt("Company id", "company_id"),
        ),
    ),
    "jira.issues.create": ActionWorkflowSchema(
        intent_label="Create Jira issue",
        required_fields=(
            _req("project key", "project_key", "project"),
            _req("summary", "summary", "title"),
        ),
        optional_fields=(
            _opt("Description", "description"),
            _opt("Assignee", "assignee", "assignee_hint", sensitive=True),
        ),
    ),
    "jira.issues.update": ActionWorkflowSchema(
        intent_label="Update Jira issue",
        required_fields=(
            _req("issue key", "issue_key", "issue_id", validator="jira_issue_ref"),
            _req("update fields", "fields", "summary", "description", validator="jira_update_payload"),
        ),
    ),
    "jira.issues.comment": ActionWorkflowSchema(
        intent_label="Comment on Jira issue",
        required_fields=(
            _req("issue key", "issue_key", "issue_id", validator="jira_issue_ref"),
            _req("comment body", "body", "comment"),
        ),
    ),
    "gmail.messages.send": ActionWorkflowSchema(
        intent_label="Send Gmail message",
        required_fields=(
            _req("recipient", "to"),
            _req("subject", "subject"),
            _req("body", "body"),
        ),
    ),
    "google_calendar.events.create": ActionWorkflowSchema(
        intent_label="Create Google Calendar event",
        required_fields=(
            _req("event title", "summary", "title"),
            _req("start time", "start", "start_time"),
        ),
        optional_fields=(_opt("End time", "end", "end_time"), _opt("Calendar", "calendar_id")),
    ),
    "google_drive.files.create": ActionWorkflowSchema(
        intent_label="Create Google Drive file",
        required_fields=(_req("file name", "name"),),
        optional_fields=(_opt("Content", "content"), _opt("MIME type", "mime_type")),
    ),
    "monday.items.create": ActionWorkflowSchema(
        intent_label="Create Monday item",
        required_fields=(
            _req("board id", "board_id"),
            _req("item name", "item_name", "name"),
        ),
    ),
    "monday.items.update": ActionWorkflowSchema(
        intent_label="Update Monday item",
        required_fields=(
            _req("board id", "board_id"),
            _req("item id", "item_id"),
            _req("column id", "column_id"),
            _req("value", "value"),
        ),
    ),
    "notion.pages.create": ActionWorkflowSchema(
        intent_label="Create Notion page",
        required_fields=(
            _req("page title", "title", "name"),
            _req("parent", "parent_id", "database_id"),
        ),
    ),
    "notion.pages.update": ActionWorkflowSchema(
        intent_label="Update Notion page",
        required_fields=(
            _req("page id", "page_id"),
            _req("update payload", "properties", "payload", validator="named_or_payload"),
        ),
    ),
    "zendesk.tickets.create": ActionWorkflowSchema(
        intent_label="Create Zendesk ticket",
        required_fields=(
            _req("subject", "subject"),
            _req("description", "comment", "body", "description", validator="zendesk_ticket_body"),
        ),
    ),
    "zendesk.tickets.update": ActionWorkflowSchema(
        intent_label="Update Zendesk ticket",
        required_fields=(
            _req("ticket id", "ticket_id"),
            _req("update fields", "properties", "payload", "comment", validator="named_or_payload"),
        ),
    ),
    "salesforce.leads.create": ActionWorkflowSchema(
        intent_label="Create Salesforce lead",
        required_fields=(_req("lead fields", "fields", "payload", validator="named_or_payload"),),
    ),
    "salesforce.tasks.create": ActionWorkflowSchema(
        intent_label="Create Salesforce task",
        required_fields=(_req("subject", "subject", "fields", validator="salesforce_task_subject"),),
    ),
    "apollo.contacts.create": ActionWorkflowSchema(
        intent_label="Create Apollo contact",
        required_fields=(
            _req(
                "contact email or name",
                "email",
                "first_name",
                "firstname",
                "payload",
                validator="named_or_payload",
                sensitive=True,
            ),
        ),
    ),
    "github.issues.create": ActionWorkflowSchema(
        intent_label="Create GitHub issue",
        required_fields=(_req("issue title", "title"),),
        optional_fields=(_opt("Body", "body"), _opt("Repository", "repo", "repository")),
    ),
    "github.pulls.create": ActionWorkflowSchema(
        intent_label="Create GitHub pull request",
        required_fields=(
            _req("PR title", "title"),
            _req("head branch", "head"),
            _req("base branch", "base"),
        ),
        optional_fields=(_opt("Body", "body"), _opt("Repository", "repo", "repository")),
    ),
    "github.issues.update": ActionWorkflowSchema(
        intent_label="Update GitHub issue",
        required_fields=(
            _req("issue number", "issue_number", "issueNumber"),
            _req("update fields", "title", "body", "state", "labels", validator="named_or_payload"),
        ),
        optional_fields=(_opt("Repository", "repo", "repository")),
    ),
    "clickup.tasks.create": ActionWorkflowSchema(
        intent_label="Create ClickUp task",
        required_fields=(
            _req("list id", "list_id"),
            _req("task name", "name"),
        ),
    ),
    "pipedrive.deals.create": ActionWorkflowSchema(
        intent_label="Create Pipedrive deal",
        required_fields=(_req("deal details", "title", "payload", "properties", validator="named_or_payload"),),
    ),
    "pipedrive.persons.create": ActionWorkflowSchema(
        intent_label="Create Pipedrive person",
        required_fields=(_req("person details", "name", "payload", "properties", validator="named_or_payload"),),
    ),
    "intercom.contacts.create": ActionWorkflowSchema(
        intent_label="Create Intercom contact",
        required_fields=(_req("contact details", "email", "payload", "properties", validator="named_or_payload"),),
    ),
    "asana.tasks.update": ActionWorkflowSchema(
        intent_label="Update Asana task",
        required_fields=(
            _req("task id", "task_id", "taskId"),
            _req("update fields", "name", "due_on", "payload", validator="asana_task_update"),
        ),
    ),
}
