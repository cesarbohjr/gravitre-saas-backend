"""Phase 2 connector write-action workflow schemas (Linear, GitLab, Shopify, PayPal, Brevo, Meta)."""
from __future__ import annotations

from app.connectors.action_catalog.models import ActionWorkflowSchema, WorkflowFieldSpec

BATCH_225_ACTION_KEYS: tuple[str, ...] = (
    "linear.issues.create",
    "linear.issues.update",
    "gitlab.issues.create",
    "gitlab.merge_requests.create",
    "shopify.products.create",
    "shopify.orders.update",
    "paypal.refunds.create",
    "paypal.payouts.create",
    "brevo.email.send",
    "brevo.contacts.create",
    "meta_marketing.campaigns.create",
    "meta_marketing.campaigns.update",
)


def _req(label: str, *keys: str, validator: str | None = None) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys, validator=validator)


def _opt(label: str, *keys: str) -> WorkflowFieldSpec:
    return WorkflowFieldSpec(label, keys)


WORKFLOW_SCHEMAS_BATCH_225: dict[str, ActionWorkflowSchema] = {
    "linear.issues.create": ActionWorkflowSchema(
        intent_label="Create Linear issue",
        required_fields=(
            _req("team id", "team_id", "teamId"),
            _req("issue title", "title", "name"),
        ),
        optional_fields=(_opt("Description", "description", "body"), _opt("Assignee", "assignee_id"),),
    ),
    "linear.issues.update": ActionWorkflowSchema(
        intent_label="Update Linear issue",
        required_fields=(
            _req("issue id", "issue_id", "id"),
            _req("update properties", "properties", "payload", "title", validator="named_or_payload"),
        ),
    ),
    "gitlab.issues.create": ActionWorkflowSchema(
        intent_label="Create GitLab issue",
        required_fields=(
            _req("project id", "project_id", "project"),
            _req("issue title", "title", "name"),
        ),
        optional_fields=(_opt("Description", "description", "body"),),
    ),
    "gitlab.merge_requests.create": ActionWorkflowSchema(
        intent_label="Create GitLab merge request",
        required_fields=(
            _req("project id", "project_id", "project"),
            _req("source branch", "source_branch", "sourceBranch"),
            _req("target branch", "target_branch", "targetBranch"),
            _req("title", "title", "name"),
        ),
    ),
    "shopify.products.create": ActionWorkflowSchema(
        intent_label="Create Shopify product",
        required_fields=(
            _req("product title", "title", "name", "properties", validator="named_or_payload"),
        ),
        optional_fields=(_opt("Product body", "body_html", "description"),),
    ),
    "shopify.orders.update": ActionWorkflowSchema(
        intent_label="Update Shopify order",
        required_fields=(
            _req("order id", "order_id", "id"),
            _req("update properties", "properties", "payload", validator="object_payload"),
        ),
    ),
    "paypal.refunds.create": ActionWorkflowSchema(
        intent_label="Issue PayPal refund",
        required_fields=(_req("capture or payment id", "capture_id", "payment_id", "id"),),
        optional_fields=(_opt("Amount", "amount"), _opt("Currency", "currency_code"),),
    ),
    "paypal.payouts.create": ActionWorkflowSchema(
        intent_label="Create PayPal payout",
        required_fields=(
            _req("sender batch id", "sender_batch_id"),
            _req("payout items", "items", "payload", validator="list_or_object_payload"),
        ),
    ),
    "brevo.email.send": ActionWorkflowSchema(
        intent_label="Send Brevo transactional email",
        required_fields=(
            _req("recipient email", "to", "email", "recipient"),
            _req("subject", "subject"),
            _req("content", "htmlContent", "textContent", "body", validator="named_or_payload"),
        ),
    ),
    "brevo.contacts.create": ActionWorkflowSchema(
        intent_label="Create Brevo contact",
        required_fields=(_req("email", "email"),),
        optional_fields=(_opt("Attributes", "attributes", "properties"),),
    ),
    "meta_marketing.campaigns.create": ActionWorkflowSchema(
        intent_label="Create Meta ad campaign",
        required_fields=(
            _req("ad account id", "ad_account_id", "account_id"),
            _req("campaign name", "name", "title"),
        ),
        optional_fields=(_opt("Objective", "objective"), _opt("Status", "status"),),
    ),
    "meta_marketing.campaigns.update": ActionWorkflowSchema(
        intent_label="Update Meta ad campaign",
        required_fields=(
            _req("campaign id", "campaign_id", "id"),
            _req("update properties", "properties", "payload", "name", validator="named_or_payload"),
        ),
    ),
}
