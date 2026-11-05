#!/usr/bin/env python3
"""Map declared connector requirements across the actual catalogs. Read-only.

Optional live inventory is a sanitized export, never a DB credential. Its item
names are replaced with ordinals in the report; no prompts/configs are emitted.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectors.catalog_dependencies import declared_dependencies, normalize_dependency
from app.connectors.nango_registry import NANGO_CONNECTOR_REGISTRY, LEGACY_NANGO_CONNECTOR_SPECS
from app.connectors.action_catalog.registry import get_vendor_catalog
from app.marketplace.seed_catalog import list_catalog_assets
from app.outcome_packs.registry import list_packs
from app.plays.catalog import STATIC_PLAY_TEMPLATES


def audit(live: dict | None = None) -> dict:
    catalog = get_vendor_catalog()
    action_vendors = set(catalog)
    text = (ROOT / "apps/web/lib/connectors.ts").read_text()
    native = {normalize_dependency(x) for x in re.findall(r'vendorKey: "([a-z0-9_]+)"', text)}
    native_oauth = set(re.findall(r'"([a-z0-9_]+)"', text.split("export const OAUTH_VENDOR_KEYS = new Set([", 1)[1].split("])", 1)[0]))
    items = []

    def add(source: str, key: str, kind: str, payload: dict) -> None:
        refs = declared_dependencies(payload, action_vendors=action_vendors)
        items.append({"source": source, "key": key, "kind": kind, "connectors": sorted(refs), "references": refs})

    for asset in list_catalog_assets():
        add("marketplace_seed", asset.slug, asset.asset_type,
            {"required_connectors": asset.required_connectors, "config": asset.config})
    for pack in list_packs():
        add("outcome_manifest", pack.pack_id, "outcome_pack", pack.raw_config)
        for play in pack.raw_config.get("plays", []):
            add("outcome_manifest", play["key"], "play", play)
        for index, agent in enumerate(pack.raw_config.get("agents", [])):
            add("outcome_manifest", f"{pack.pack_id}:agent:{index}", "ai_agent", agent)
    for play in STATIC_PLAY_TEMPLATES:
        add("platform_play", play.key, "play", asdict(play))
    for vendor in catalog.values():
        for workflow in vendor.demo_workflows:
            add("connector_workflow", f"{vendor.vendor}:{workflow.id}", "workflow", workflow.to_dict(vendor=vendor.vendor))
    for kind, rows in (live or {}).items():
        if kind not in {"agents", "assets", "workflows", "packages", "plays"} or not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            # Private names never enter a commit. Public slugs are already
            # independently represented by repository catalog entries above.
            add("live_snapshot", f"{kind}:{index + 1}", kind, row)

    dependencies = []
    for vendor in sorted({v for item in items for v in item["connectors"]}):
        spec = NANGO_CONNECTOR_REGISTRY.get(vendor)
        if vendor in {"platform", "webhook", "vapi"}:
            state = "internal_platform_not_external_connector"
        elif vendor in {"fhir", "real_estate"}:
            state = "generic_adapter_requires_specific_provider_selection"
        elif vendor in {"brevo", "connectwise", "engagebay"}:
            state = "existing_backend_no_reviewed_interactive_oauth_template"
        elif spec and spec.auth_mode in {"OAUTH1", "OAUTH2"}:
            state = "managed_oauth_implemented_activation_unverified"
        elif vendor in native_oauth:
            state = "native_oauth_preserved_live_grant_unverified"
        elif spec:
            state = "managed_provider_has_no_interactive_oauth_mapping"
        elif vendor in native:
            state = "existing_native_or_specialized_connector"
        else:
            state = "missing_catalog_connector_requires_provider_review"
        dependencies.append({"vendor": vendor, "state": state,
                             "integration_id": spec.integration_id if spec else None,
                             "provider": spec.provider if spec else None,
                             "used_by": [f"{i['source']}:{i['kind']}:{i['key']}" for i in items if vendor in i["connectors"]]})
    return {"scope": "declared_dependencies_not_inferred_recommendations_or_live_acceptance",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "counts": {"items": len(items), "sources": dict(Counter(i["source"] for i in items)),
                       "kinds": dict(Counter(i["kind"] for i in items)), "vendors": len(dependencies)},
            "oauth_upgrades": {key: {"old_integration": value.integration_id,
                                      "new_integration": NANGO_CONNECTOR_REGISTRY[key].integration_id}
                               for key, value in LEGACY_NANGO_CONNECTOR_SPECS.items()},
            "dependencies": dependencies, "items": items}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-inventory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.live_inventory.read_text()) if args.live_inventory else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["counts"], indent=2))
