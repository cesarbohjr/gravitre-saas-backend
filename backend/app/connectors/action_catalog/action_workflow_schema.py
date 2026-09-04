"""Declarative chat workflow schemas keyed by catalog action id."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

ASANA_TASKS_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Create Asana task",
    known_defaults=(("Task type", "Asana task"),),
    required_fields=(
        WorkflowFieldSpec(
            "task title",
            ("name",),
            validator="asana_task_title",
        ),
        WorkflowFieldSpec("project", ("project", "project_id")),
        WorkflowFieldSpec(
            "due date",
            ("due_on",),
            sensitive=True,
            inferrable=False,
        ),
    ),
    optional_fields=(
        WorkflowFieldSpec(
            "Assignee",
            ("assignee_hint", "assignee"),
            sensitive=True,
            inferrable=False,
        ),
    ),
)

APOLLO_LISTS_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Create Apollo contact list",
    required_fields=(WorkflowFieldSpec("list name", ("name", "list_name")),),
    optional_fields=(WorkflowFieldSpec("Modality", ("modality",)),),
)

APOLLO_LISTS_ADD_SCHEMA = ActionWorkflowSchema(
    intent_label="Add contacts to Apollo list",
    required_fields=(
        WorkflowFieldSpec("contact ids", ("entity_ids", "contact_ids", "ids")),
        WorkflowFieldSpec("list name", ("label_names", "list_names", "list_name", "name")),
    ),
    optional_fields=(WorkflowFieldSpec("Modality", ("modality",)),),
)

HUBSPOT_CONTACTS_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Create HubSpot contact",
    required_fields=(
        WorkflowFieldSpec(
            "email or contact name",
            ("email", "firstname", "properties"),
            validator="hubspot_contact_identity",
            sensitive=True,
        ),
    ),
    optional_fields=(
        WorkflowFieldSpec("First name", ("firstname",)),
        WorkflowFieldSpec("Last name", ("lastname",)),
    ),
)

HUBSPOT_ASSOCIATIONS_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Associate HubSpot CRM objects",
    required_fields=(
        WorkflowFieldSpec("from object type", ("from_type", "fromType")),
        WorkflowFieldSpec("from object id", ("from_id", "fromId")),
        WorkflowFieldSpec("to object type", ("to_type", "toType")),
        WorkflowFieldSpec("to object id", ("to_id", "toId")),
    ),
)

HUBSPOT_COMPANIES_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Create HubSpot company",
    required_fields=(
        WorkflowFieldSpec(
            "company name or domain",
            ("name", "domain", "properties"),
        ),
    ),
    optional_fields=(
        WorkflowFieldSpec("Domain", ("domain",)),
        WorkflowFieldSpec("Industry", ("industry",)),
    ),
)

HUBSPOT_CAMPAIGNS_UPDATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Update HubSpot marketing campaign",
    required_fields=(
        WorkflowFieldSpec("campaign id", ("campaign_id", "id")),
        WorkflowFieldSpec(
            "update properties",
            ("properties", "payload", "name", "subject"),
            validator="named_or_payload",
        ),
    ),
)

CONNECTWISE_TICKETS_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Create ConnectWise service ticket",
    required_fields=(
        WorkflowFieldSpec("ticket summary", ("summary", "subject")),
        WorkflowFieldSpec("board id", ("board_id", "boardId")),
    ),
    optional_fields=(
        WorkflowFieldSpec("Company record id", ("company_record_id", "companyRecordId")),
        WorkflowFieldSpec("Description", ("description", "body")),
        WorkflowFieldSpec("Priority id", ("priority_id",)),
    ),
)

SLACK_POST_MESSAGE_SCHEMA = ActionWorkflowSchema(
    intent_label="Post Slack message",
    required_fields=(
        # Channel is Slack's entity-resolution target (assignee/email analogue for Memory).
        WorkflowFieldSpec("channel", ("channel",), sensitive=True),
        WorkflowFieldSpec("message", ("text", "message")),
    ),
)

SLACK_CONVERSATIONS_JOIN_SCHEMA = ActionWorkflowSchema(
    intent_label="Join Slack channel",
    required_fields=(
        WorkflowFieldSpec("channel", ("channel", "channel_id"), sensitive=True),
    ),
)

VAPI_CALLS_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Start outbound Vapi AI phone call",
    required_fields=(
        WorkflowFieldSpec("assistant id", ("assistant_id",)),
        WorkflowFieldSpec(
            "customer phone number",
            ("customer", "number", "phone"),
            sensitive=True,
        ),
    ),
    optional_fields=(
        WorkflowFieldSpec("phone number id", ("phone_number_id",), sensitive=True),
    ),
)

GOOGLE_ADS_CAMPAIGNS_UPDATE_BUDGET_SCHEMA = ActionWorkflowSchema(
    intent_label="Update Google Ads campaign budget",
    required_fields=(
        WorkflowFieldSpec(
            "campaign",
            ("campaign_id", "campaignId", "campaign_name", "name"),
            sensitive=True,
        ),
        WorkflowFieldSpec(
            "daily budget",
            ("daily_budget", "amount_micros", "amountMicros"),
        ),
    ),
)

GOOGLE_ADS_CAMPAIGNS_PAUSE_SCHEMA = ActionWorkflowSchema(
    intent_label="Pause Google Ads campaign",
    required_fields=(
        WorkflowFieldSpec(
            "campaign",
            ("campaign_id", "campaignId", "campaign_name", "name"),
            sensitive=True,
        ),
    ),
)

GOOGLE_ADS_CAMPAIGNS_RESUME_SCHEMA = ActionWorkflowSchema(
    intent_label="Resume Google Ads campaign",
    required_fields=(
        WorkflowFieldSpec(
            "campaign",
            ("campaign_id", "campaignId", "campaign_name", "name"),
            sensitive=True,
        ),
    ),
)

GOOGLE_ADS_STRUCTURE_CREATE_SCHEMA = ActionWorkflowSchema(
    intent_label="Create Google Ads Search campaign structure",
    required_fields=(
        WorkflowFieldSpec(
            "total daily budget",
            ("daily_budget_total", "dailyBudgetTotal", "total_daily_budget"),
        ),
        WorkflowFieldSpec(
            "campaigns",
            ("campaigns",),
            validator="list_or_object_payload",
        ),
    ),
    optional_fields=(
        WorkflowFieldSpec("negative keywords", ("negative_keywords", "negativeKeywords")),
        WorkflowFieldSpec("conversion actions", ("conversion_actions", "conversionActions")),
    ),
)

_TEST_SCHEMA_REGISTRY: dict[str, ActionWorkflowSchema] = {}


def register_workflow_schema(action_key: str, schema: ActionWorkflowSchema) -> None:
    """Register a workflow schema override (used in tests)."""
    _TEST_SCHEMA_REGISTRY[action_key.strip().lower()] = schema


def clear_workflow_schema_registry() -> None:
    _TEST_SCHEMA_REGISTRY.clear()


def get_workflow_schema(action_key: str) -> ActionWorkflowSchema | None:
    key = action_key.strip().lower()
    if key in _TEST_SCHEMA_REGISTRY:
        return _TEST_SCHEMA_REGISTRY[key]
    from app.connectors.action_catalog.workflow_schemas_batch_25 import WORKFLOW_SCHEMAS_BATCH_25

    if key in WORKFLOW_SCHEMAS_BATCH_25:
        return WORKFLOW_SCHEMAS_BATCH_25[key]
    from app.connectors.action_catalog.workflow_schemas_batch_50 import WORKFLOW_SCHEMAS_BATCH_50

    if key in WORKFLOW_SCHEMAS_BATCH_50:
        return WORKFLOW_SCHEMAS_BATCH_50[key]
    from app.connectors.action_catalog.workflow_schemas_batch_75 import WORKFLOW_SCHEMAS_BATCH_75

    if key in WORKFLOW_SCHEMAS_BATCH_75:
        return WORKFLOW_SCHEMAS_BATCH_75[key]
    from app.connectors.action_catalog.workflow_schemas_batch_100 import WORKFLOW_SCHEMAS_BATCH_100

    if key in WORKFLOW_SCHEMAS_BATCH_100:
        return WORKFLOW_SCHEMAS_BATCH_100[key]
    from app.connectors.action_catalog.workflow_schemas_batch_125 import WORKFLOW_SCHEMAS_BATCH_125

    if key in WORKFLOW_SCHEMAS_BATCH_125:
        return WORKFLOW_SCHEMAS_BATCH_125[key]
    from app.connectors.action_catalog.workflow_schemas_batch_150 import WORKFLOW_SCHEMAS_BATCH_150

    if key in WORKFLOW_SCHEMAS_BATCH_150:
        return WORKFLOW_SCHEMAS_BATCH_150[key]
    from app.connectors.action_catalog.workflow_schemas_batch_175 import WORKFLOW_SCHEMAS_BATCH_175

    if key in WORKFLOW_SCHEMAS_BATCH_175:
        return WORKFLOW_SCHEMAS_BATCH_175[key]
    from app.connectors.action_catalog.workflow_schemas_batch_200 import WORKFLOW_SCHEMAS_BATCH_200

    if key in WORKFLOW_SCHEMAS_BATCH_200:
        return WORKFLOW_SCHEMAS_BATCH_200[key]
    from app.connectors.action_catalog.workflow_schemas_batch_225 import WORKFLOW_SCHEMAS_BATCH_225

    if key in WORKFLOW_SCHEMAS_BATCH_225:
        return WORKFLOW_SCHEMAS_BATCH_225[key]
    from app.connectors.action_catalog.registry import get_action_spec

    spec = get_action_spec(key)
    if spec and spec.workflow_schema:
        return spec.workflow_schema
    return None


def iter_workflow_fields(schema: ActionWorkflowSchema):
    """Yield required then optional fields (tolerates a bare WorkflowFieldSpec)."""
    for group in (schema.required_fields, schema.optional_fields):
        if group is None:
            continue
        if isinstance(group, WorkflowFieldSpec):
            yield group
            continue
        for field in group:
            yield field


def list_non_inferrable_arg_keys(action_key: str) -> frozenset[str]:
    schema = get_workflow_schema(action_key)
    if not schema:
        return frozenset()
    keys: set[str] = set()
    for field in iter_workflow_fields(schema):
        if field.sensitive or not field.inferrable:
            keys.update(field.arg_keys)
    return frozenset(keys)
