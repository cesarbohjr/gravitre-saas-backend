#!/usr/bin/env python3
"""Audit published marketplace assets against the install-ready + binding gate.

Writes docs/delivery/published-pack-install-ready-audit.json (repo root relative).
Does not talk to production DB — evaluates seeded catalog assets in-process.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.marketplace.install_ready import evaluate_binding_install_ready, merge_install_ready  # noqa: E402
from app.marketplace.seed_catalog import list_catalog_assets  # noqa: E402


def _asset_row(asset) -> dict:
    return {
        "slug": asset.slug,
        "title": asset.title,
        "asset_type": asset.asset_type,
        "status": "published",
        "config": asset.config,
        "install_variables": asset.install_variables,
        "required_connectors": asset.required_connectors,
    }


def main() -> int:
    assets = list_catalog_assets()
    rows = []
    fail_codes: Counter[str] = Counter()
    for asset in assets:
        row = _asset_row(asset)
        binding = evaluate_binding_install_ready(row)
        # Seed audit assumes connectors connected — isolate binding honesty.
        merged = merge_install_ready(connector_can_install=True, asset=row)
        for err in binding["installReadyErrors"]:
            fail_codes[str(err.get("code") or "unknown")] += 1
        rows.append(
            {
                "slug": asset.slug,
                "assetType": asset.asset_type,
                "installReady": merged["installReady"],
                "hasWorkflowBindings": binding["hasWorkflowBindings"],
                "installReadyErrors": binding["installReadyErrors"],
                "manualSetupRequired": merged["manualSetupRequired"],
                "requiredConnectors": [
                    {
                        "connectorType": c.get("connectorType"),
                        "required": c.get("required"),
                    }
                    for c in (asset.required_connectors or [])
                    if isinstance(c, dict)
                ],
            }
        )

    failed = [r for r in rows if not r["installReady"]]
    msp = next((r for r in rows if r["slug"] == "msp-prospects-clay-hubspot-enrichment"), None)
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "seed_catalog.list_catalog_assets",
        "total": len(rows),
        "installReadyPass": len(rows) - len(failed),
        "installReadyFail": len(failed),
        "topErrorCodes": fail_codes.most_common(20),
        "failedSlugs": [r["slug"] for r in failed],
        "mspEnrichment": msp,
        "deferredRemediation": {
            "note": (
                "Part 2 finish (2026-08-03): former Slice A binding failures remediated "
                "(hubspot.contacts.search rename + TICKET_ID install vars). failCount=0 means clear."
            ),
            "failCount": len(failed),
            "remediatedSlugs": [
                "hubspot-lead-qualification",
                "customer-health-monitoring",
                "zendesk-ticket-triage",
                "lead-routing-automation",
                "qbr-preparation-workflow",
                "support-operations-pack",
            ],
        },
        "assets": rows,
    }
    out = ROOT / "docs" / "delivery" / "published-pack-install-ready-audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(f"pass={report['installReadyPass']} fail={report['installReadyFail']}")
    if msp:
        print(
            "msp-prospects-clay-hubspot-enrichment installReady=",
            msp.get("installReady"),
            "required=",
            msp.get("requiredConnectors"),
        )
    return 0 if msp and msp.get("installReady") else 1


if __name__ == "__main__":
    raise SystemExit(main())
