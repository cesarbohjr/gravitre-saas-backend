#!/usr/bin/env python3
"""STA-276: Tier 1 connector capability audit (OAuth prod + tool coverage)."""
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
TIER1_VENDORS = [
    "hubspot",
    "salesforce",
    "slack",
    "jira",
    "zendesk",
    "microsoft365",
    "google_analytics",
    "google_calendar",
    "gmail",
    "google_drive",
    "google_docs",
    "google_sheets",
]


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
    for tier in ("v1", "v2", "v3"):
        actions.extend(catalog["tiers"][tier]["actions"])
    missing = [a["tool"] for a in actions if not a["implemented"]]
    oauth = fetch_oauth_status(vendor)
    return {
        "vendor": vendor,
        "displayName": catalog["displayName"],
        "catalogActions": len(actions),
        "implementedActions": len(actions) - len(missing),
        "missingTools": missing,
        "oauth": oauth,
        "demoReady": oauth["ready"] and len(missing) == 0,
        "partialDemo": oauth["ready"] and len(missing) < len(actions),
    }


def main() -> int:
    results = [audit_vendor(v) for v in TIER1_VENDORS]
    full_demo = [r for r in results if r["demoReady"]]
    oauth_gaps = [r["vendor"] for r in results if not r["oauth"]["ready"]]
    tool_gaps = [r for r in results if r["missingTools"]]

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "issue": "STA-276",
        "apiBase": API_BASE,
        "summary": {
            "vendorsAudited": len(results),
            "fullDemoReady": len(full_demo),
            "oauthGaps": oauth_gaps,
            "toolGapVendors": [r["vendor"] for r in tool_gaps if r["missingTools"]],
        },
        "supabase": {
            "note": "Not a customer OAuth connector — platform auth/storage via Supabase; org data via PostgreSQL source connector.",
            "platformAuth": "Supabase Auth (login callback on supabase.co)",
            "dataSurface": "postgresql source connector + RAG knowledge sync",
        },
        "vendors": results,
    }

    out_path = REPO_ROOT / "docs" / "delivery" / "tier1-connector-audit-latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Tier 1 audit: {len(full_demo)}/{len(results)} full demo-ready")
    print(f"OAuth gaps: {', '.join(oauth_gaps) or 'none'}")
    for row in results:
        status = "OK" if row["demoReady"] else ("PARTIAL" if row["partialDemo"] else "GAP")
        print(
            f"  {row['displayName']:20} {status:7} "
            f"tools {row['implementedActions']}/{row['catalogActions']} "
            f"oauth={'ready' if row['oauth']['ready'] else 'gap'}"
        )
    print(f"\nReport: {out_path}")
    return 0 if not oauth_gaps else 1


if __name__ == "__main__":
    raise SystemExit(main())
