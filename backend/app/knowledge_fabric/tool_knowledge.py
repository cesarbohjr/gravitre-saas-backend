"""Tool expertise knowledge — Gravitre-authored content attached to existing connectors.

Stored once per vendor (pack.tool.{vendor}), consumed by any department agent
that has been granted that connector. Not a parallel Observation/Action/Governance system.
"""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.integration_taxonomy import tool_knowledge_pack_id
from app.knowledge_fabric.registry import KnowledgeSourceSpec

# Original Gravitre-authored expertise (facts / standard practice — not vendor prose copies).
# License: Gravitre original; commercial use allowed; licence_verified at authoring.
_TOOL_DOCS: dict[str, list[dict[str, Any]]] = {
    "hubspot": [
        {
            "external_id": "hubspot-objects-overview",
            "title": "HubSpot CRM object model (Gravitre summary)",
            "topics": ("crm", "contacts", "companies", "deals", "associations"),
            "content": (
                "HubSpot CRM centers on Contacts, Companies, Deals, Tickets, and custom objects. "
                "Contacts associate to Companies; Deals associate to Contacts and Companies. "
                "Pipelines and deal stages are pipeline-scoped — updating a deal stage requires a "
                "valid stage id for that pipeline. Properties are typed (string, number, date, "
                "enumeration); unknown property names fail the API. Use search/list before create "
                "to avoid duplicates on email. Rate limits apply per app and account — backoff on "
                "429. Private apps use bearer tokens; OAuth apps need refresh handling. "
                "Common errors: INVALID_PROPERTY, RATE_LIMIT, CONFLICT on unique email, and "
                "missing association type ids when linking records."
            ),
        },
        {
            "external_id": "hubspot-workflows-and-lists",
            "title": "HubSpot lists and enrollment patterns (Gravitre summary)",
            "topics": ("lists", "workflows", "enrollment", "marketing"),
            "content": (
                "Static and active lists segment contacts for marketing and sales motions. "
                "Enrollment into workflows is a write that can trigger emails — treat as "
                "approval-sensitive in Gravitre. Prefer reading list membership and contact "
                "properties before mutating. Marketing emails and bulk enrollment are higher "
                "blast-radius than single contact updates. When tools fail, check portal "
                "scopes (crm.objects.contacts.write vs marketing scopes) before retrying."
            ),
        },
    ],
    "salesforce": [
        {
            "external_id": "salesforce-objects-overview",
            "title": "Salesforce core objects (Gravitre summary)",
            "topics": ("crm", "leads", "accounts", "opportunities", "soql"),
            "content": (
                "Salesforce CRM typically flows Lead → Account/Contact → Opportunity. "
                "Record types and page layouts vary by org. SOQL queries are used for search; "
                "governor limits apply. Stage names on Opportunities are org-configured picklists. "
                "API errors often include REQUIRED_FIELD_MISSING, INVALID_FIELD, and "
                "ENTITY_IS_DELETED. Bulk updates should stay under batch limits. Connected apps "
                "need the correct OAuth scopes for the objects being read or written."
            ),
        }
    ],
    "slack": [
        {
            "external_id": "slack-channels-messaging",
            "title": "Slack channels and messaging (Gravitre summary)",
            "topics": ("channels", "messaging", "threads", "rate_limits"),
            "content": (
                "Slack workspaces organize conversations in channels and DMs. Posting messages "
                "requires channel membership and chat:write (or equivalent). Thread replies use "
                "thread_ts. Rate limits are tiered by method — chat.postMessage is commonly "
                "tier 3/4. Errors include not_in_channel, channel_not_found, and invalid_auth. "
                "Prefer listing conversations before posting to a guessed channel name."
            ),
        }
    ],
    "stripe": [
        {
            "external_id": "stripe-billing-objects",
            "title": "Stripe customers, payments, refunds (Gravitre summary)",
            "topics": ("customers", "payments", "refunds", "idempotency"),
            "content": (
                "Stripe models Customers, PaymentIntents/Charges, Invoices, and Refunds. "
                "Refunds and payouts are high-blast-radius writes — Gravitre treats them as "
                "destructive/approval-gated. Use idempotency keys on creates. Test mode keys "
                "must not hit live money. Common errors: resource_missing, card_error, "
                "idempotency_key reuse with different params, and insufficient permissions "
                "on restricted keys."
            ),
        }
    ],
    "notion": [
        {
            "external_id": "notion-pages-databases",
            "title": "Notion pages and databases (Gravitre summary)",
            "topics": ("pages", "databases", "blocks", "properties"),
            "content": (
                "Notion content is a tree of pages and blocks; databases are pages with "
                "structured properties. Queries filter on property types (title, select, "
                "relation). Integrations only see pages shared with the integration. "
                "Property schema mismatches cause validation errors. Prefer querying a "
                "database before creating rows with required properties."
            ),
        }
    ],
    "github": [
        {
            "external_id": "github-issues-prs",
            "title": "GitHub issues and pull requests (Gravitre summary)",
            "topics": ("issues", "pull_requests", "repos", "permissions"),
            "content": (
                "GitHub resources are scoped by owner/repo. Issues and PRs have states "
                "(open/closed); merges and force operations need elevated permissions. "
                "Secondary rate limits apply under abuse detection. Common failures: 404 "
                "for private repos without access, 422 validation, and 403 on protected "
                "branches. List before mutate when referencing issue numbers."
            ),
        }
    ],
    "jira": [
        {
            "external_id": "jira-issues-transitions",
            "title": "Jira issues and transitions (Gravitre summary)",
            "topics": ("issues", "transitions", "projects", "jql"),
            "content": (
                "Jira issues belong to projects with workflows that define legal transitions. "
                "Transitioning an issue requires a valid transition id for the current status. "
                "JQL searches projects the user can browse. Custom fields vary by project. "
                "Errors include transition not available, required field missing, and "
                "permission denied on project browse/edit."
            ),
        }
    ],
    "sendgrid": [
        {
            "external_id": "sendgrid-mail-send",
            "title": "SendGrid mail send patterns (Gravitre summary)",
            "topics": ("email", "templates", "suppression", "deliverability"),
            "content": (
                "SendGrid sends transactional or marketing mail via API keys with mail.send "
                "scope. Templates use dynamic template data. Suppressions (bounces, unsubscribes) "
                "block delivery. Sending is high blast-radius — approval-gated in Gravitre. "
                "Watch 401 invalid key, 403 forbidden, and 429 rate limits. Verify from-domain "
                "authentication before production sends."
            ),
        }
    ],
    "zendesk": [
        {
            "external_id": "zendesk-tickets",
            "title": "Zendesk tickets (Gravitre summary)",
            "topics": ("tickets", "users", "support", "statuses"),
            "content": (
                "Zendesk Support centers on Tickets linked to Users/Organizations. Status "
                "transitions (new/open/pending/solved/closed) follow business rules. "
                "Comments can be public or internal. Merging tickets is destructive. "
                "API tokens need the right role. Common errors: RecordInvalid, "
                "Forbidden, and rate limit (429)."
            ),
        }
    ],
    "google_analytics": [
        {
            "external_id": "ga4-properties-reports",
            "title": "GA4 properties and reports (Gravitre summary)",
            "topics": ("analytics", "properties", "reports", "dimensions"),
            "content": (
                "GA4 organizes data under Accounts → Properties → Data streams. Reports "
                "run against property ids with dimensions/metrics combinations that must be "
                "compatible. Customer entitlement (property access) gates what Gravitre can "
                "query even when the API is open. Quotas apply per property. Prefer listing "
                "properties before running reports on a guessed id."
            ),
        }
    ],
}


def tool_knowledge_vendors() -> tuple[str, ...]:
    return tuple(sorted(_TOOL_DOCS.keys()))


def tool_packs_for_connected_vendors(connected: list[str] | None) -> list[str]:
    """Map granted connectors → tool expertise packs (single source, many consumers)."""
    out: list[str] = []
    for raw in connected or []:
        vendor = str(raw or "").strip().lower()
        if vendor in _TOOL_DOCS:
            pid = tool_knowledge_pack_id(vendor)
            if pid not in out:
                out.append(pid)
    return out


def tool_knowledge_source_specs() -> tuple[KnowledgeSourceSpec, ...]:
    specs: list[KnowledgeSourceSpec] = []
    for vendor in tool_knowledge_vendors():
        pack = tool_knowledge_pack_id(vendor)
        specs.append(
            KnowledgeSourceSpec(
                source_id=f"tool.{vendor}.expertise",
                publisher="Gravitre",
                url=f"https://gravitre.ai/tool-knowledge/{vendor}",
                source_type="tool_expertise",
                department="tool_expertise",
                industry=None,
                topics=("tool_expertise", vendor, "connector", "best_practices"),
                jurisdictions=(),
                ingestion_method="bulk",
                license_type="A",
                commercial_use_allowed=True,
                attribution_required=False,
                crawl_allowed=False,
                refresh_frequency="version_change",
                authority_score=0.86,
                quality_score=0.85,
                pack_id=pack,
                pack_label=f"{vendor.replace('_', ' ').title()} Tool Expertise",
                license="Gravitre-Original",
                license_url="https://gravitre.ai/legal",
                derivatives_allowed=True,
                third_party_content_present=False,
                legal_review_status="verified_live",
                licence_verified=True,
                refresh_days=90,
                citation_required=True,
                license_notes=(
                    "Gravitre-authored original summaries of standard product practice. "
                    "Not a copy of vendor documentation prose. Vendor docs were NOT "
                    "bulk-ingested (A–E commercial-use gate)."
                ),
            )
        )
    return tuple(specs)


async def fetch_tool_knowledge_documents(
    spec: KnowledgeSourceSpec,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    vendor = (spec.source_id.split(".")[1] if "." in spec.source_id else "").lower()
    docs = _TOOL_DOCS.get(vendor) or []
    out: list[dict[str, Any]] = []
    for doc in docs[:limit]:
        out.append(
            {
                "external_id": f"{vendor}-{doc['external_id']}",
                "title": doc["title"],
                "content": doc["content"],
                "citation": f"Gravitre tool expertise — {vendor} — {doc['title']}",
                "jurisdiction": None,
                "topics": list(doc.get("topics") or []) + [vendor, "tool_expertise"],
                "metadata": {
                    "license_type": "A",
                    "license": "Gravitre-Original",
                    "pack_type": "tool_expertise",
                    "vendor": vendor,
                    "content_mode": "gravitre_authored_original",
                },
            }
        )
    return out
