#!/usr/bin/env python3
"""STA-282: Tier 4 connector capability audit — SharePoint (M365), Intercom."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.connectors.action_catalog.registry import get_vendor_catalog_dict  # noqa: E402
from app.connectors.simulation_coverage import (  # noqa: E402
    DEMO_EXCLUDED_VENDORS,
    HRIS_REFERENCE_VENDOR,
    TIER4_MICROSOFT365_V4_PREFIX,
)

API_BASE = "https://api.gravitre.app"
TIER4_VENDORS = ["intercom", "microsoft365", HRIS_REFERENCE_VENDOR]
TIERS = ("v1", "v2", "v3", "v4")


def fetch_oauth_status(vendor: str) -> dict:
    url = f"{API_BASE}/api/connectors/oauth/{vendor}/status"
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=20) as resp:
            data = json.loads(resp.read().decode())
        return {
            "configured": bool(data.get("configured")),
            "encryptionConfigured": bool(data.get("encryptionConfigured")),
            "redirectUri": data.get("redirectUri"),
            "ready": bool(data.get("configured") and data.get("encryptionConfigured")),
        }
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "configured": False,
            "encryptionConfigured": False,
            "redirectUri": None,
            "ready": False,
            "error": str(exc),
        }


def audit_vendor(vendor: str) -> dict:
    catalog = get_vendor_catalog_dict(vendor)
    actions = []
    v1_actions = []
    sharepoint_actions = []
    for tier in TIERS:
        tier_block = catalog["tiers"].get(tier)
        if tier_block:
            tier_actions = tier_block["actions"]
            actions.extend(tier_actions)
            if tier == "v1":
                v1_actions = list(tier_actions)
            if vendor == "microsoft365" and tier == "v4":
                sharepoint_actions = [
                    a
                    for a in tier_actions
                    if TIER4_MICROSOFT365_V4_PREFIX in str(a.get("tool", ""))
                ]
    missing = [a["tool"] for a in actions if not a["implemented"]]
    missing_v1 = [a["tool"] for a in v1_actions if not a["implemented"]]
    oauth = fetch_oauth_status(vendor)
    return {
        "vendor": vendor,
        "displayName": catalog["displayName"],
        "shipped": catalog["shipped"],
        "catalogActions": len(actions),
        "implementedActions": len(actions) - len(missing),
        "missingTools": missing,
        "sharePointV4Actions": len(sharepoint_actions),
        "sharePointV4Implemented": sum(1 for a in sharepoint_actions if a["implemented"]),
        "demoExcluded": vendor in DEMO_EXCLUDED_VENDORS,
        "hrisReference": vendor == HRIS_REFERENCE_VENDOR,
        "oauth": oauth,
        "demoReadyRead": oauth["ready"] and len(missing_v1) == 0 and vendor not in DEMO_EXCLUDED_VENDORS,
        "demoReadyFull": oauth["ready"] and len(missing) == 0 and catalog["shipped"],
        "partnerEmbeddedNote": (
            "SharePoint + Intercom are partner/embedded tier — approval-gated writes; "
            "reads OK for pilot demos when OAuth ready."
        ),
    }


def main() -> int:
    results = [audit_vendor(v) for v in TIER4_VENDORS]
    read_ready = [r for r in results if r["demoReadyRead"]]
    sharepoint = next((r for r in results if r["vendor"] == "microsoft365"), None)

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "issue": "STA-282",
        "apiBase": API_BASE,
        "scope": {
            "tier4Partners": ["SharePoint (microsoft365 v4)", "Intercom"],
            "hrisReference": HRIS_REFERENCE_VENDOR,
            "workdayExcluded": sorted(DEMO_EXCLUDED_VENDORS),
        },
        "summary": {
            "vendorsAudited": len(results),
            "readDemoReady": len(read_ready),
            "sharePointV4Implemented": sharepoint["sharePointV4Implemented"] if sharepoint else 0,
            "sharePointV4Catalog": sharepoint["sharePointV4Actions"] if sharepoint else 0,
        },
        "vendors": results,
        "references": {
            "hrisPattern": "docs/integration/HRIS_REFERENCE_PATTERN.md",
            "simulationCoverage": "docs/delivery/demo-simulation-coverage-latest.json",
        },
    }

    out_path = REPO_ROOT / "docs" / "delivery" / "tier4-connector-audit-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Tier 4 audit: {len(read_ready)}/{len(results)} read demo-ready")
    if sharepoint:
        print(
            f"  SharePoint v4: {sharepoint['sharePointV4Implemented']}/"
            f"{sharepoint['sharePointV4Actions']} tools implemented"
        )
    for row in results:
        status = "OK" if row["demoReadyRead"] else "GAP"
        print(
            f"  {row['displayName']:20} {status:4} "
            f"tools {row['implementedActions']}/{row['catalogActions']} "
            f"oauth={'ready' if row['oauth']['ready'] else 'gap'}"
        )
    print(f"\nReport: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
