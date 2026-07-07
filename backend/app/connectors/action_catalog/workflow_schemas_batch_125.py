"""Priority write-action workflow schemas — batch 5 of pending_schema shrink (25 actions)."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

BATCH_125_ACTION_KEYS: tuple[str, ...] = (
    "google_analytics.audiences.create",
    "google_analytics.conversions.create",
    "mongodb.documents.insert",
    "mongodb.documents.update",
    "postgresql.query.insert",
    "postgresql.query.update",
    "snowflake.query.insert",
    "snowflake.stages.put",
    "mixpanel.events.track",
    "mixpanel.profiles.set",
    "odoo.invoices.create",
    "odoo.partners.create",
    "odoo.sales.orders.create",
    "netsuite.customers.update",
    "netsuite.journalentries.create",
    "pagerduty.incidents.add_note",
    "motion.tasks.update",
    "n8n.workflows.create",
    "n8n.workflows.activate",
    "zapier.hooks.trigger",
    "zapier.zaps.enable",
    "linkedin.leads.submit",
    "linkedin.audience.update",
    "apollo.sequences.add",
    "aws_s3.objects.put",
)


def _req(label: str, *keys: str, validator: str | None = None) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, validator=validator)


def _opt(label: str, *keys: str) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys)


WORKFLOW_SCHEMAS_BATCH_125: dict[str, ActionWorkflowSchema] = {
    "google_analytics.audiences.create": ActionWorkflowSchema(
        intent_label="Create Google Analytics audience",
        required_fields=(
            _req("property id", "property_id"),
            _req("audience name", "display_name", "name"),
        ),
    ),
    "google_analytics.conversions.create": ActionWorkflowSchema(
        intent_label="Create Google Analytics conversion",
        required_fields=(
            _req("property id", "property_id"),
            _req("event name", "event_name", "name"),
        ),
    ),
    "mongodb.documents.insert": ActionWorkflowSchema(
        intent_label="Insert MongoDB documents",
        required_fields=(
            _req("database", "database", "db"),
            _req("collection", "collection"),
            _req("documents", "documents", "payload", validator="list_or_object_payload"),
        ),
    ),
    "mongodb.documents.update": ActionWorkflowSchema(
        intent_label="Update MongoDB documents",
        required_fields=(
            _req("database", "database", "db"),
            _req("collection", "collection"),
            _req("filter or update", "filter", "query", "update", "payload", validator="object_payload"),
        ),
    ),
    "postgresql.query.insert": ActionWorkflowSchema(
        intent_label="Insert PostgreSQL rows",
        required_fields=(
            _req("table", "table"),
            _req("rows or query", "rows", "values", "query", "payload", validator="list_or_object_payload"),
        ),
    ),
    "postgresql.query.update": ActionWorkflowSchema(
        intent_label="Update PostgreSQL rows",
        required_fields=(
            _req("table", "table"),
            _req("update payload", "set", "values", "query", "payload", validator="object_payload"),
        ),
    ),
    "snowflake.query.insert": ActionWorkflowSchema(
        intent_label="Insert Snowflake rows",
        required_fields=(
            _req("table", "table"),
            _req("rows or query", "rows", "values", "query", "payload", validator="list_or_object_payload"),
        ),
    ),
    "snowflake.stages.put": ActionWorkflowSchema(
        intent_label="Upload file to Snowflake stage",
        required_fields=(
            _req("stage", "stage", "stage_name"),
            _req("file path or content", "path", "file", "content", validator="named_or_payload"),
        ),
    ),
    "mixpanel.events.track": ActionWorkflowSchema(
        intent_label="Track Mixpanel event",
        required_fields=(_req("event name", "event", "event_name"),),
        optional_fields=(_opt("Distinct id", "distinct_id"), _opt("Properties", "properties"),),
    ),
    "mixpanel.profiles.set": ActionWorkflowSchema(
        intent_label="Set Mixpanel profile properties",
        required_fields=(
            _req("distinct id", "distinct_id"),
            _req("profile properties", "properties", "payload", validator="object_payload"),
        ),
    ),
    "odoo.invoices.create": ActionWorkflowSchema(
        intent_label="Create Odoo invoice",
        required_fields=(_req("partner id", "partner_id"),),
        optional_fields=(_opt("Invoice lines", "lines", "payload"),),
    ),
    "odoo.partners.create": ActionWorkflowSchema(
        intent_label="Create Odoo partner",
        required_fields=(_req("partner name", "name", "payload", validator="named_or_payload"),),
    ),
    "odoo.sales.orders.create": ActionWorkflowSchema(
        intent_label="Create Odoo sales order",
        required_fields=(_req("partner id", "partner_id"),),
        optional_fields=(_opt("Order lines", "lines", "payload"),),
    ),
    "netsuite.customers.update": ActionWorkflowSchema(
        intent_label="Update NetSuite customer",
        required_fields=(
            _req("customer id", "customer_id"),
            _req("update fields", "fields", "payload", validator="object_payload"),
        ),
    ),
    "netsuite.journalentries.create": ActionWorkflowSchema(
        intent_label="Create NetSuite journal entry",
        required_fields=(_req("entry payload", "entry", "payload", "fields", validator="object_payload"),),
    ),
    "pagerduty.incidents.add_note": ActionWorkflowSchema(
        intent_label="Add PagerDuty incident note",
        required_fields=(
            _req("incident id", "incident_id", "id"),
            _req("note", "note", "content", "body"),
        ),
    ),
    "motion.tasks.update": ActionWorkflowSchema(
        intent_label="Update Motion task",
        required_fields=(
            _req("task id", "task_id"),
            _req("update payload", "payload", "properties", validator="object_payload"),
        ),
    ),
    "n8n.workflows.create": ActionWorkflowSchema(
        intent_label="Create n8n workflow",
        required_fields=(_req("workflow definition", "name", "nodes", "payload", validator="named_or_payload"),),
    ),
    "n8n.workflows.activate": ActionWorkflowSchema(
        intent_label="Activate n8n workflow",
        required_fields=(_req("workflow id", "workflow_id", "id"),),
    ),
    "zapier.hooks.trigger": ActionWorkflowSchema(
        intent_label="Trigger Zapier hook",
        required_fields=(_req("hook url or payload", "url", "hook_url", "payload", validator="named_or_payload"),),
    ),
    "zapier.zaps.enable": ActionWorkflowSchema(
        intent_label="Enable Zapier Zap",
        required_fields=(_req("zap id", "zap_id", "id"),),
    ),
    "linkedin.leads.submit": ActionWorkflowSchema(
        intent_label="Submit LinkedIn lead",
        required_fields=(_req("lead payload", "lead", "payload", "fields", validator="object_payload"),),
    ),
    "linkedin.audience.update": ActionWorkflowSchema(
        intent_label="Update LinkedIn audience",
        required_fields=(
            _req("audience id", "audience_id", "id"),
            _req("update fields", "payload", "fields", validator="object_payload"),
        ),
    ),
    "apollo.sequences.add": ActionWorkflowSchema(
        intent_label="Add contacts to Apollo sequence",
        required_fields=(
            _req("sequence id", "sequence_id"),
            _req("contact ids", "contact_ids", "contacts", validator="list_or_object_payload"),
        ),
    ),
    "aws_s3.objects.put": ActionWorkflowSchema(
        intent_label="Upload S3 object",
        required_fields=(
            _req("bucket", "bucket"),
            _req("object key", "key", "object_key"),
            _req("content", "body", "content", validator="named_or_payload"),
        ),
    ),
}
