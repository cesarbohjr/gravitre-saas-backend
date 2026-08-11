"""Five-class integration taxonomy — metadata on the existing catalog, not a parallel system.

Classes describe how Gravitre / the customer gains API access. They do not replace
ActionSpec kind/destructive/requires_approval governance.
"""
from __future__ import annotations

from typing import Any, Literal

IntegrationClass = Literal[
    "OPEN_API",
    "OPEN_API_CUSTOMER_ENTITLEMENT",
    "DEVELOPER_APPROVAL",
    "MCP_AVAILABLE",
    "LICENSED_PARTNER_ONLY",
]

INTEGRATION_CLASSES: frozenset[str] = frozenset(
    {
        "OPEN_API",
        "OPEN_API_CUSTOMER_ENTITLEMENT",
        "DEVELOPER_APPROVAL",
        "MCP_AVAILABLE",
        "LICENSED_PARTNER_ONLY",
    }
)

# Official vendor MCP exists, but native ActionSpec connectors are preferred.
_MCP_AVAILABLE_PREFER_NATIVE: frozenset[str] = frozenset(
    {"notion", "asana", "clickup", "monday"}
)

# Customer SaaS plan / property entitlements gate usable surface area.
_CUSTOMER_ENTITLEMENT: frozenset[str] = frozenset(
    {
        "google_analytics",
        "google_search_console",
        "microsoft365",
        "microsoft_teams",
        "outlook",
        "gmail",
        "google_drive",
        "google_docs",
        "google_sheets",
        "google_calendar",
        "quickbooks",
        "xero",
        "aws_s3",
    }
)

# Not in catalog yet — classification for Phase 0 missing vendors (planning only).
_MISSING_VENDOR_CLASS: dict[str, IntegrationClass] = {
    "gitlab": "OPEN_API",
    "trello": "OPEN_API",
    "linear": "OPEN_API",
    "paypal": "OPEN_API_CUSTOMER_ENTITLEMENT",
    "shopify": "OPEN_API_CUSTOMER_ENTITLEMENT",
    "woocommerce": "OPEN_API",
    "wordpress": "OPEN_API",
    "brevo": "OPEN_API",
    "meta_marketing": "DEVELOPER_APPROVAL",
    "cloudflare": "OPEN_API",
    "azure": "OPEN_API_CUSTOMER_ENTITLEMENT",
    "google_cloud": "OPEN_API_CUSTOMER_ENTITLEMENT",
}


def get_integration_class(vendor: str) -> IntegrationClass:
    v = (vendor or "").strip().lower()
    if v in _MCP_AVAILABLE_PREFER_NATIVE:
        return "MCP_AVAILABLE"
    if v in _CUSTOMER_ENTITLEMENT:
        return "OPEN_API_CUSTOMER_ENTITLEMENT"
    if v in _MISSING_VENDOR_CLASS:
        return _MISSING_VENDOR_CLASS[v]
    # Default for shipped open REST/GraphQL connectors
    return "OPEN_API"


def mcp_preference_for_vendor(vendor: str) -> dict[str, Any]:
    """Whether official MCP should replace the native connector (Phase 2)."""
    v = (vendor or "").strip().lower()
    if v not in _MCP_AVAILABLE_PREFER_NATIVE:
        return {
            "vendor": v,
            "official_mcp_known": False,
            "prefer": "n/a",
            "reason": "No Wave-1 official MCP classification for this vendor.",
        }
    return {
        "vendor": v,
        "official_mcp_known": True,
        "prefer": "native_actionspec",
        "reason": (
            "Native ActionSpec + API connector already live in the 696-action catalog; "
            "MCP remains an optional org overlay via mcp_catalog_sync — do not duplicate."
        ),
    }


def tool_knowledge_pack_id(vendor: str) -> str:
    return f"pack.tool.{(vendor or '').strip().lower()}"


def classify_wave1_report() -> list[dict[str, Any]]:
    """Full Wave 1 classification rows for delivery evidence."""
    covered = [
        "hubspot",
        "salesforce",
        "google_analytics",
        "google_search_console",
        "gmail",
        "google_drive",
        "slack",
        "github",
        "asana",
        "clickup",
        "monday",
        "notion",
        "jira",
        "confluence",
        "airtable",
        "stripe",
        "quickbooks",
        "xero",
        "mailchimp",
        "sendgrid",
        "zendesk",
        "intercom",
        "aws_s3",
        "microsoft365",
    ]
    rows = []
    for v in covered:
        rows.append(
            {
                "vendor": v,
                "in_catalog": True,
                "integration_class": get_integration_class(v),
                "tool_knowledge_pack_id": tool_knowledge_pack_id(v),
                "mcp": mcp_preference_for_vendor(v),
            }
        )
    for v, cls in _MISSING_VENDOR_CLASS.items():
        rows.append(
            {
                "vendor": v,
                "in_catalog": False,
                "integration_class": cls,
                "tool_knowledge_pack_id": None,
                "mcp": mcp_preference_for_vendor(v),
                "note": "No ActionSpecs — tool knowledge deferred until connector exists",
            }
        )
    return rows
