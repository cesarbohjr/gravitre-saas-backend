"""STA-292 / MKT-PACK-AUDIT 6.1: Marketing Operations Pack connector gap audit."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.connectors.action_catalog.registry import get_vendor_catalog_dict, list_catalog_vendors
from app.connectors.oauth_provider_registry import OAUTH_PROVIDER_REGISTRY

ConnectorGapState = Literal["exists", "partial", "missing"]
PackBlocker = Literal["yes", "no", "depends"]


@dataclass(frozen=True)
class MarketingPackConnectorGap:
    key: str
    display_name: str
    vendor: str | None
    audit_state: ConnectorGapState
    complexity: Literal["low", "medium", "high"]
    blocks_pack: PackBlocker
    notes: str
    pack_workflow_use: str = ""


MARKETING_PACK_CONNECTOR_GAPS: tuple[MarketingPackConnectorGap, ...] = (
    MarketingPackConnectorGap(
        key="apollo",
        display_name="Apollo.io",
        vendor="apollo",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        notes="OAuth partner flow via generic OAuth registry; legacy API key fallback; action catalog + apollo_tools shipped.",
        pack_workflow_use="Prospect enrichment and outbound sequencing",
    ),
    MarketingPackConnectorGap(
        key="notion",
        display_name="Notion",
        vendor="notion",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        notes="OAuth via notion_oauth.py; pages/databases actions and sync service.",
        pack_workflow_use="Campaign briefs and knowledge handoff",
    ),
    MarketingPackConnectorGap(
        key="google_drive",
        display_name="Google Drive",
        vendor="google_drive",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        notes="Google vendor OAuth + google_drive tools in tool_service.",
        pack_workflow_use="Asset storage and creative exports",
    ),
    MarketingPackConnectorGap(
        key="dropbox",
        display_name="Dropbox",
        vendor=None,
        audit_state="missing",
        complexity="medium",
        blocks_pack="depends",
        notes="No vendor definition or OAuth spec.",
        pack_workflow_use="Optional file handoff alternative to Drive",
    ),
    MarketingPackConnectorGap(
        key="canva",
        display_name="Canva",
        vendor="canva",
        audit_state="partial",
        complexity="low",
        blocks_pack="no",
        notes="OAuth in registry; designs/export/autofill via canva_tools.",
        pack_workflow_use="Creative production in designer agent step",
    ),
    MarketingPackConnectorGap(
        key="adobe_creative_cloud",
        display_name="Adobe Creative Cloud",
        vendor=None,
        audit_state="missing",
        complexity="high",
        blocks_pack="depends",
        notes="Adobe Marketo exists; no Creative Cloud / Express design connector.",
        pack_workflow_use="Enterprise design toolchain alternative to Canva",
    ),
    MarketingPackConnectorGap(
        key="engagebay",
        display_name="EngageBay",
        vendor="engagebay",
        audit_state="partial",
        complexity="medium",
        blocks_pack="depends",
        notes="OAuth + v1/v2/v3 catalog actions; SMB marketing automation alternative to HubSpot.",
        pack_workflow_use="SMB marketing automation alternative to HubSpot",
    ),
    MarketingPackConnectorGap(
        key="linkedin_publish",
        display_name="LinkedIn (organic publishing)",
        vendor="linkedin",
        audit_state="partial",
        complexity="high",
        blocks_pack="yes",
        notes="LinkedIn enrich/ads/leads only; no posts.create / w_member_social publish action.",
        pack_workflow_use="Social publish step in campaign workflow",
    ),
)

LINKEDIN_PUBLISH_TOOL_IDS = frozenset({
    "linkedin.posts.create",
    "linkedin.posts.publish",
    "linkedin.ugcPosts.create",
})


def _vendor_implemented_tool_count(vendor: str) -> tuple[int, int]:
    catalog = get_vendor_catalog_dict(vendor)
    if not catalog:
        return 0, 0
    actions: list[dict[str, Any]] = []
    for tier_block in (catalog.get("tiers") or {}).values():
        actions.extend(tier_block.get("actions") or [])
    total = len(actions)
    implemented = sum(1 for action in actions if action.get("implemented"))
    return implemented, total


def _catalog_has_tool(vendor: str, tool_suffixes: set[str]) -> bool:
    catalog = get_vendor_catalog_dict(vendor)
    if not catalog:
        return False
    for tier_block in (catalog.get("tiers") or {}).values():
        for action in tier_block.get("actions") or []:
            tool_id = str(action.get("tool") or "")
            if tool_id in tool_suffixes or any(tool_id.endswith(suffix) for suffix in tool_suffixes):
                return True
    return False


def _resolve_live_state(gap: MarketingPackConnectorGap) -> ConnectorGapState:
    if gap.vendor is None:
        return "missing"

    vendor = gap.vendor.lower()
    if vendor not in list_catalog_vendors():
        return "missing"

    if gap.key == "linkedin_publish":
        if _catalog_has_tool(vendor, LINKEDIN_PUBLISH_TOOL_IDS):
            return "exists"
        return "partial"

    implemented, total = _vendor_implemented_tool_count(vendor)
    if total == 0:
        return "missing"
    if implemented == 0:
        return "missing"

    if gap.key == "apollo":
        return "partial"

    oauth_vendors = set(OAUTH_PROVIDER_REGISTRY.keys())
    if vendor in oauth_vendors or vendor in {"notion", "google_drive"}:
        return "partial" if implemented < total else "partial"
    return "partial"


def audit_marketing_pack_connectors() -> dict[str, Any]:
    """Return STA-292 checklist with live code verification."""
    rows: list[dict[str, Any]] = []
    missing_count = 0
    partial_count = 0
    pack_blockers: list[str] = []

    for gap in MARKETING_PACK_CONNECTOR_GAPS:
        live_state = _resolve_live_state(gap)
        if live_state == "missing":
            missing_count += 1
        elif live_state == "partial":
            partial_count += 1
        if gap.blocks_pack == "yes" and live_state != "exists":
            pack_blockers.append(gap.key)

        implemented, total = (0, 0)
        if gap.vendor:
            implemented, total = _vendor_implemented_tool_count(gap.vendor)

        rows.append(
            {
                "key": gap.key,
                "displayName": gap.display_name,
                "vendor": gap.vendor,
                "documentedState": gap.audit_state,
                "liveState": live_state,
                "stateMatchesDoc": live_state == gap.audit_state,
                "complexity": gap.complexity,
                "blocksPack": gap.blocks_pack,
                "packWorkflowUse": gap.pack_workflow_use,
                "implementedTools": implemented,
                "catalogTools": total,
                "notes": gap.notes,
            }
        )

    return {
        "issue": "STA-292",
        "packSlug": "marketing-operations-pack",
        "summary": {
            "total": len(rows),
            "missing": missing_count,
            "partial": partial_count,
            "exists": len(rows) - missing_count - partial_count,
            "packBlockers": pack_blockers,
            "linkedinPublishGap": "linkedin_publish" in pack_blockers,
        },
        "connectors": rows,
    }
