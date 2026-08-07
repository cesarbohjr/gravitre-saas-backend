#!/usr/bin/env python3
"""Phase 2 — audit published packs for full pre-wiring (edges + non-stub prompts).

Distinct from connector install-ready. Writes:
  docs/delivery/published-pack-prewiring-audit.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.marketplace.pack_prewiring import evaluate_pack_prewiring  # noqa: E402
from app.marketplace.seed_catalog import list_catalog_assets  # noqa: E402


def _asset_row(asset) -> dict:
    return {
        "slug": asset.slug,
        "title": asset.title,
        "asset_type": asset.asset_type,
        "status": "published",
        "config": asset.config,
        "install_variables": [
            row if isinstance(row, dict) else getattr(row, "__dict__", {})
            for row in (asset.install_variables or [])
        ],
        "required_connectors": asset.required_connectors,
    }


def main() -> int:
    assets = list_catalog_assets()
    rows = []
    fail_codes: Counter[str] = Counter()
    for asset in assets:
        row = evaluate_pack_prewiring(_asset_row(asset))
        for err in row.get("errors") or []:
            fail_codes[str(err.get("code") or "unknown")] += 1
        rows.append(row)

    scoped = [r for r in rows if r["verdict"] != "N_A"]
    passed = [r for r in scoped if r["verdict"] == "PASS"]
    failed = [r for r in scoped if r["verdict"] == "FAIL"]
    with_manual = [r for r in passed if r.get("manualSetupRequired")]

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "seed_catalog.list_catalog_assets",
        "phase": "phase2_pack_prewiring",
        "totalCatalogAssets": len(rows),
        "workflowBearingAudited": len(scoped),
        "fullyPrewiredPass": len(passed),
        "prewiringFail": len(failed),
        "passWithHonestManualSetup": len(with_manual),
        "fixedInThisPassNote": (
            "Stub agent tasks expanded; install embeds definition.graph and "
            "materializes canvas via sync_builder_graph."
        ),
        "topErrorCodes": fail_codes.most_common(20),
        "failedSlugs": [r["slug"] for r in failed],
        "assets": rows,
    }
    out = ROOT / "docs" / "delivery" / "published-pack-prewiring-audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(
        f"audited={report['workflowBearingAudited']} "
        f"pass={report['fullyPrewiredPass']} fail={report['prewiringFail']}"
    )
    if failed:
        print("failed:", ", ".join(report["failedSlugs"][:30]))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
