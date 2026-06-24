#!/usr/bin/env python3
"""STA-277: Tier 2 connector capability audit (QuickBooks, NetSuite)."""
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

API_BASE = "https://api.gravitre.app"
TIER2_VENDORS = ["quickbooks", "netsuite"]
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
        return {"configured": False, "encryptionConfigured": False, "redirectUri": None, "ready": False, "error": str(exc)}


def audit_vendor(vendor: str) -> dict:
    catalog = get_vendor_catalog_dict(vendor)
    actions = []
    v1_actions = []
    for tier in TIERS:
        tier_block = catalog["tiers"].get(tier)
        if tier_block:
            actions.extend(tier_block["actions"])
            if tier == "v1":
                v1_actions = list(tier_block["actions"])
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
        "oauth": oauth,
        "demoReadyRead": oauth["ready"] and len(missing_v1) == 0,
        "demoReadyFull": oauth["ready"] and len(missing) == 0 and catalog["shipped"],
        "pilotDefault": "v1 live reads; v2/v3 writes approval-gated (simulation layer in STA-285)",
    }


def main() -> int:
    results = [audit_vendor(v) for v in TIER2_VENDORS]
    read_ready = [r for r in results if r["demoReadyRead"]]
    full_ready = [r for r in results if r["demoReadyFull"]]
    oauth_gaps = [r["vendor"] for r in results if not r["oauth"]["ready"]]
    tool_gaps = [r for r in results if r["missingTools"]]

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "issue": "STA-277",
        "apiBase": API_BASE,
        "summary": {
            "vendorsAudited": len(results),
            "readDemoReady": len(read_ready),
            "fullDemoReady": len(full_ready),
            "oauthGaps": oauth_gaps,
            "toolGapVendors": [r["vendor"] for r in tool_gaps if r["missingTools"]],
            "pilotWritePolicy": "Financial connectors default to read-only demos; writes require customer IT approval or Phase 3 simulation (STA-285).",
        },
        "scopeVerification": {
            "doc": "docs/delivery/tier2-scope-verification.md",
        },
        "oauthSmoke": {
            "doc": "docs/delivery/tier2-oauth-smoke-latest.json",
            "command": "npm run tier2:smoke",
        },
        "vendors": results,
    }

    out_path = REPO_ROOT / "docs" / "delivery" / "tier2-connector-audit-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Tier 2 audit: {len(full_ready)}/{len(results)} full demo-ready, {len(read_ready)}/{len(results)} read-ready")
    print(f"OAuth gaps: {', '.join(oauth_gaps) or 'none'}")
    for row in results:
        status = "OK" if row["demoReadyFull"] else ("READ" if row["demoReadyRead"] else "GAP")
        print(
            f"  {row['displayName']:20} {status:4} "
            f"tools {row['implementedActions']}/{row['catalogActions']} "
            f"oauth={'ready' if row['oauth']['ready'] else 'gap'}"
        )
    print(f"\nReport: {out_path}")
    return 0 if not tool_gaps else 1


if __name__ == "__main__":
    raise SystemExit(main())
