"""Demo-safe simulation coverage registry by connector tier (STA-285)."""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.registry import (
    get_vendor_catalog_dict,
    list_catalog_vendors,
)

# Phase 2 audit groupings — aligned with scripts/check-tier*-connector-audit.py
CONNECTOR_AUDIT_TIERS: dict[str, list[str]] = {
    "tier1": [
        "hubspot",
        "salesforce",
        "slack",
        "microsoft365",
        "google",
        "jira",
        "zendesk",
        "supabase",
    ],
    "tier2": ["quickbooks", "netsuite"],
    "tier3": ["asana", "monday", "clickup"],
    "tier4": ["intercom"],  # SharePoint actions live under microsoft365 vendor
}

# Vendors excluded from live demos (STA-280)
DEMO_EXCLUDED_VENDORS: frozenset[str] = frozenset({"workday"})

# HRIS reference for demos (STA-280)
HRIS_REFERENCE_VENDOR = "bamboohr"

# Tier 2 writes blocked for live demos without fixtures — simulation/twin only
FINANCIAL_WRITE_DEMO_BLOCKED = True

# SharePoint v4 tools are audited under microsoft365 (tool ids: microsoft365.sharepoint.*)
TIER4_MICROSOFT365_V4_PREFIX = ".sharepoint."


def _vendor_audit_tier(vendor: str) -> str | None:
    key = vendor.lower().strip()
    for tier, vendors in CONNECTOR_AUDIT_TIERS.items():
        if key in vendors:
            return tier
    if key == HRIS_REFERENCE_VENDOR:
        return "tier4"
    if key in DEMO_EXCLUDED_VENDORS:
        return "excluded"
    return None


def _action_kind(action: dict[str, Any]) -> str:
    return str(action.get("kind") or "read")


def evaluate_action_demo_safety(vendor: str, action: dict[str, Any]) -> dict[str, Any]:
    """Classify whether an action is safe for live demos vs simulation-only."""
    tool = str(action.get("tool") or "")
    kind = _action_kind(action)
    implemented = bool(action.get("implemented"))
    tier = _vendor_audit_tier(vendor) or "unclassified"
    destructive = bool(action.get("destructive"))
    requires_approval = bool(action.get("requiresApproval"))

    simulation_modes: list[str] = []
    if implemented:
        simulation_modes.append("llm_predict")  # digital_twin always available
        simulation_modes.append("fixture_replay")
    if kind == "read" and implemented:
        simulation_modes.append("live_read")

    demo_blocked = False
    reasons: list[str] = []

    if vendor.lower() in DEMO_EXCLUDED_VENDORS:
        demo_blocked = True
        reasons.append("vendor_excluded_from_demos")
    if not implemented:
        demo_blocked = True
        reasons.append("tool_not_implemented")
    if tier == "tier2" and kind in {"write", "advanced"} and FINANCIAL_WRITE_DEMO_BLOCKED:
        demo_blocked = True
        reasons.append("tier2_financial_write_simulation_only")
    if destructive and not requires_approval and kind != "read":
        demo_blocked = True
        reasons.append("destructive_without_approval_gate")

    live_demo_safe = implemented and not demo_blocked and (
        kind == "read" or (requires_approval and tier not in {"tier2"})
    )

    return {
        "tool": tool,
        "kind": kind,
        "implemented": implemented,
        "auditTier": tier,
        "simulationModes": simulation_modes,
        "simulationCoverage": "full" if implemented else "none",
        "liveDemoSafe": live_demo_safe,
        "demoBlocked": demo_blocked,
        "demoBlockedReasons": reasons,
    }


def evaluate_vendor_demo_safety(vendor: str) -> dict[str, Any]:
    catalog = get_vendor_catalog_dict(vendor.lower().strip())
    if not catalog:
        return {"vendor": vendor, "found": False}

    actions_report: list[dict[str, Any]] = []
    blocked_tools: list[str] = []
    for tier_block in catalog.get("tiers", {}).values():
        for action in tier_block.get("actions", []):
            row = evaluate_action_demo_safety(vendor, action)
            actions_report.append(row)
            if row["demoBlocked"]:
                blocked_tools.append(row["tool"])

    read_safe = sum(1 for r in actions_report if r["liveDemoSafe"] and r["kind"] == "read")
    zero_coverage = [r["tool"] for r in actions_report if r["simulationCoverage"] == "none"]

    return {
        "vendor": vendor,
        "displayName": catalog["displayName"],
        "found": True,
        "auditTier": _vendor_audit_tier(vendor),
        "demoExcluded": vendor.lower() in DEMO_EXCLUDED_VENDORS,
        "hrisReference": vendor.lower() == HRIS_REFERENCE_VENDOR,
        "actionCount": len(actions_report),
        "liveDemoSafeReads": read_safe,
        "demoBlockedTools": blocked_tools,
        "zeroCoverageTools": zero_coverage,
        "demoReady": len(zero_coverage) == 0 and vendor.lower() not in DEMO_EXCLUDED_VENDORS,
        "actions": actions_report,
    }


def build_simulation_coverage_report() -> dict[str, Any]:
    """Full registry for API and audit scripts."""
    vendors = []
    demo_blocked_vendors: list[str] = []
    zero_coverage_vendors: list[str] = []

    for vendor in list_catalog_vendors():
        row = evaluate_vendor_demo_safety(vendor)
        vendors.append(row)
        if row.get("demoExcluded"):
            demo_blocked_vendors.append(vendor)
        if row.get("zeroCoverageTools"):
            zero_coverage_vendors.append(vendor)

    # SharePoint v4 slice under microsoft365 (STA-282)
    m365 = next((v for v in vendors if v["vendor"] == "microsoft365"), None)
    sharepoint_actions: list[dict[str, Any]] = []
    if m365:
        sharepoint_actions = [
            a for a in m365["actions"] if TIER4_MICROSOFT365_V4_PREFIX in a["tool"]
        ]

    return {
        "issue": "STA-285",
        "policy": {
            "zeroCoverageEqualsDemoBlocked": True,
            "tier2WriteLiveDemoBlocked": FINANCIAL_WRITE_DEMO_BLOCKED,
            "digitalTwinFallback": "llm_predict for all implemented tools",
            "fixtureReplay": "connector_fixtures table",
        },
        "demoExcludedVendors": sorted(DEMO_EXCLUDED_VENDORS),
        "hrisReferenceVendor": HRIS_REFERENCE_VENDOR,
        "summary": {
            "vendorCount": len(vendors),
            "demoReadyVendors": sum(1 for v in vendors if v.get("demoReady")),
            "demoBlockedVendorCount": len(demo_blocked_vendors),
            "zeroCoverageVendorCount": len(zero_coverage_vendors),
        },
        "sharePointV4Actions": sharepoint_actions,
        "vendors": vendors,
    }
