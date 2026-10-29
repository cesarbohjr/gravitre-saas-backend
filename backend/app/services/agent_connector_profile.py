"""Versioned progressive connector guidance shared by every agent surface.

This describes setup and source availability, never executable authority. All
reads/writes still pass invoke_tool's current account, IAM, scope, quota,
approval, cancellation and receipt gates. No recommendations create grants.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode
from app.core.safe_dict import safe_normalize_stored_dict

SCHEMA_VERSION = 1
# Supported setup routes already exist in the Connectors catalog. Unknown
# vendors fail closed; presence of a catalog-only name is not implementation.
CONNECTORS = {
    "hubspot": ("HubSpot", "Use authorized CRM audiences, contacts and pipeline evidence."),
    "salesforce": ("Salesforce", "Review authorized accounts, opportunities and pipeline records."),
    "google_analytics": ("Google Analytics", "Measure observed traffic and conversions for the selected property."),
    "google_ads": ("Google Ads", "Review authorized paid-search and display account evidence."),
    "google_search_console": ("Google Search Console", "Review authorized search visibility and page performance."),
    "canva": ("Canva", "Work with authorized design and brand assets."),
    "zendesk": ("Zendesk", "Review authorized tickets and support context."),
    "intercom": ("Intercom", "Review authorized customer conversations and support context."),
    "quickbooks": ("QuickBooks", "Reconcile authorized financial records."),
    "stripe": ("Stripe", "Review authorized payment and subscription evidence."),
    "jira": ("Jira", "Review authorized issues and delivery progress."),
    "github": ("GitHub", "Review authorized software repositories and pull requests."),
    "confluence": ("Confluence", "Use authorized team documentation."),
    "notion": ("Notion", "Use authorized project notes and knowledge pages."),
    "slack": ("Slack", "Use authorized team conversations and approved communications."),
    "google_drive": ("Google Drive", "Use authorized source documents and files."),
    "google_sheets": ("Google Sheets", "Use authorized spreadsheet evidence."),
    "google_calendar": ("Google Calendar", "Review authorized schedules and meetings."),
    "gmail": ("Gmail", "Work with authorized mail; sends remain approval-gated."),
    "apollo": ("Apollo", "Use authorized prospecting and list evidence within the account's API tier."),
    "clay": ("Clay", "Use authorized enrichment workflows and supplied lead records."),
    "bamboohr": ("BambooHR", "Use authorized people operations records."),
    "greenhouse": ("Greenhouse", "Use authorized recruiting and application records."),
    "pagerduty": ("PagerDuty", "Review authorized software incidents and on-call context."),
    "connectwise": ("ConnectWise", "Review authorized software service tickets."),
    "asana": ("Asana", "Review authorized project tasks and owners."),
    "monday": ("monday.com", "Review authorized work boards and delivery status."),
    "clickup": ("ClickUp", "Review authorized tasks and project dependencies."),
    "microsoft365": ("Microsoft 365", "Use authorized workspace documents and communications."),
    "outlook": ("Outlook", "Use authorized mail and calendar context."),
    "netsuite": ("NetSuite", "Review authorized financial and operational records."),
    "workday": ("Workday", "Review authorized people operations context."),
}
PLATFORM_SOURCES = {"platform", "fred", "nvd", "cisa_kev", "sec_edgar"}
# Domain-specific ordering; legacy/custom agents retain their existing systems
# as recommendations. No source flag or recommendation changes tool grants.
PRIORITIES = {
    "ppc-campaign-strategist": ("google_ads", "google_analytics"),
    "programmatic-display-buyer": ("google_ads", "google_analytics", "dsp"),
    "paid-social-strategist": ("hubspot", "meta_ads", "tiktok_ads", "linkedin_ads"),
    "seo-analyst": ("google_analytics", "google_search_console", "google_ads"),
    "marketing-analyst": ("google_ads", "google_analytics", "hubspot"),
    "marketing-ops-coordinator": ("hubspot", "google_analytics"),
    "marketing-designer": ("canva",),
}
UNSUPPORTED = {"meta_ads":"Meta Ads", "tiktok_ads":"TikTok Ads", "linkedin_ads":"LinkedIn Ads", "dsp":"Demand-side buying platform"}
OFFLINE = ["Discuss strategy and plan next steps", "Draft and review content", "Analyze evidence you provide or upload"]


def agent_definition(agent: dict[str, Any]) -> dict[str, Any]:
    """Accept published asset config or an installed agent; never mutate it."""
    if agent.get("asset_type") == "ai_agent":
        return safe_normalize_stored_dict(agent.get("config"))
    return agent


def recommendations(agent: dict[str, Any]) -> dict[str, Any]:
    definition = agent_definition(agent)
    config = safe_normalize_stored_dict(definition.get("config"))
    slug = str(config.get("marketplaceSlug") or agent.get("slug") or "")
    systems = definition.get("systems")
    from app.capabilities.operations_roles import role_for_slug as operations_role_for_slug

    from app.capabilities.software_roles import role_for_slug as software_role_for_slug

    software_role = software_role_for_slug(slug)
    operations_role = operations_role_for_slug(slug)
    types = list(PRIORITIES.get(slug, ()))
    if operations_role:
        types.extend(operations_role["connectors"])
    if software_role:
        types.extend(software_role["connectors"])
    if isinstance(systems, list):
        types.extend(str(s).strip().lower() for s in systems if isinstance(s, str))
    for ref in agent.get("required_connectors", []) if isinstance(agent.get("required_connectors"), list) else []:
        if isinstance(ref, dict):
            types.append(str(ref.get("connectorType") or ref.get("connector_type") or ""))
    # Deduplicate preserving curated priority, never rank every available app.
    types = list(dict.fromkeys(t for t in types if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", t) and t not in PLATFORM_SOURCES))[:8]
    rows = []
    for i, vendor in enumerate(types):
        from app.connectors.nango_registry import get_nango_connector_spec
        from app.connectors.action_catalog.registry import get_vendor_spec

        managed = get_nango_connector_spec(vendor)
        catalog = get_vendor_spec(vendor)
        managed_supported = bool(managed and managed.provider and catalog and catalog.all_actions())
        supported = vendor in CONNECTORS or managed_supported
        fallback = ((managed.display_name, "Use authorized records through the managed connector; individual action readiness is checked at execution.")
                    if managed_supported else (UNSUPPORTED.get(vendor, vendor.replace("_", " ").title()), "This integration is not supported for governed execution yet."))
        label, benefit = CONNECTORS.get(vendor, fallback)
        # legacy defaults must never supply an unsupported connect link.
        rows.append({"connectorType": vendor, "label": label, "priority": i+1,
                     "group": "first" if i == 0 else "next" if i == 1 else "optional",
                     "purpose": benefit, "capabilities": [benefit], "supported": supported,
                     "required": False, "requiredForExecution": True,
                     "connectPath": ("/connectors?" + urlencode({"type": vendor, **({"agentId": agent["id"]} if agent.get("id") and agent.get("asset_type") != "ai_agent" else {})})) if supported else None})
    return {"schemaVersion": SCHEMA_VERSION, "recommendations": rows, "offlineCapabilities": list(OFFLINE),
            "noIntegrationRationale": None if rows else "This agent can work from conversation and supplied evidence; no external integration is needed for its advisory role.",
            "authorityNote": "Connection status is not permission to execute. Account access, scopes, IAM, quotas and write approvals are checked for every action."}


def resolve_profile(agent: dict[str, Any], *, org_id: str, connectors: list[dict[str, Any]]) -> dict[str, Any]:
    if not org_id or (agent.get("asset_type") != "ai_agent" and agent.get("org_id") not in (None, org_id)) or (agent.get("asset_type") == "ai_agent" and agent.get("visibility") in {"private", "internal"} and agent.get("org_id") != org_id):
        raise ValueError("agent_connector_scope_mismatch")
    profile = recommendations(agent)
    for item in profile["recommendations"]:
        rows = [r for r in connectors if isinstance(r, dict) and r.get("org_id") == org_id
                and (r.get("type") or r.get("vendor")) == item["connectorType"] and not r.get("deleted_at")]
        active = any(str(r.get("status") or "").lower() in {"active", "connected", "healthy"} for r in rows)
        state = ("not_supported" if not item["supported"] else "connected" if active
                 else "needs_attention" if rows else "available")
        item.update(state=state, connected=state == "connected", ready=state == "connected", canExecute=False,
                    stateLabel={"not_supported":"Not supported yet", "connected":"Connected", "needs_attention":"Needs attention", "available":"Available to connect"}[state])
    return profile


def load_profile(client: Any, org_id: str, agent: dict[str, Any], *, environment_name: str = "production") -> dict[str, Any]:
    resolve_profile(agent, org_id=org_id, connectors=[])
    # Fresh reads: no per-agent cache that can retain a revoked connection.
    try:
        rows = (client.table("connectors").select("org_id,type,status,deleted_at,environment_name")
                .eq("org_id", org_id).eq("environment_name", environment_name).execute().data or [])
    except Exception:
        result = resolve_profile(agent, org_id=org_id, connectors=[])
        for row in result["recommendations"]:
            if row["supported"]:
                row.update(state="needs_attention",stateLabel="Needs attention",connected=False,ready=False)
        return result
    return resolve_profile(agent, org_id=org_id, connectors=rows)


def prompt_section(agent: dict[str, Any]) -> str:
    """Identical guidance in full/classical and compact/unified/voice prompts."""
    profile = recommendations(agent)
    lines = ["Progressive connector guidance: this agent is useful without connected apps.",
             "No connectors needed: " + "; ".join(profile["offlineCapabilities"]) + ".", profile["authorityNote"],
             "For a relevant request, suggest only the smallest needed connector set. Respect declined or dismissed suggestions; do not repeatedly nag."]
    for item in profile["recommendations"]:
        group = {"first":"Recommended first", "next":"Recommended next", "optional":"Optional"}[item["group"]]
        lines.append(f"{group}: {item['label']} — {item['purpose']} " + (f"Connect at {item['connectPath']}; current account readiness must be checked." if item["supported"] else "Not supported yet; no connect action."))
    return "\n".join(lines)
