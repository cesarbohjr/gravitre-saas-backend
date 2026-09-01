"""Does HubSpot's own OpenAPI contract require filterGroups on object search?

Our tool layer refuses hubspot.deals.search without a non-empty filter_groups,
in two places, and the refusal is ours — HubSpot never sent it. A live call with
the real token can only be made from production (local env has no HubSpot OAuth
client credentials), so this reads the vendor's published, machine-readable
contract instead: whatever `required` says on the search request schema is the
vendor's actual rule.

This is the same spec source the Phase 5 drift scan is meant to diff against.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "delivery" / "hubspot-search-vendor-contract.json"
CATALOG = "https://api.hubspot.com/public/api/spec/v1/specs"
WANTED = {"Deals", "Contacts", "Companies", "Tickets"}


def main() -> int:
    cat = httpx.get(CATALOG, timeout=60.0, follow_redirects=True).json()
    entries = cat if isinstance(cat, list) else (cat.get("results") or [])
    findings: list[dict] = []

    for entry in entries:
        name = entry.get("name")
        if name not in WANTED:
            continue
        versions = entry.get("versions") or []
        # Prefer the stable/latest non-beta version.
        version = next(
            (v for v in versions if (v.get("stage") or "").upper() == "LATEST" and "beta" not in str(v.get("version", "")).lower()),
            versions[0] if versions else None,
        )
        if not version or not version.get("openApi"):
            print(f"{name}: no openApi url")
            continue
        url = version["openApi"]
        print(f"\n=== {name} (version {version.get('version')}) ===")
        print(f"spec: {url}")
        try:
            spec = httpx.get(url, timeout=90.0, follow_redirects=True).json()
        except Exception as exc:  # noqa: BLE001
            print(f"  spec fetch failed: {exc}")
            continue

        paths = spec.get("paths") or {}
        search_paths = [p for p in paths if p.rstrip("/").endswith("/search")]
        print(f"  search paths: {search_paths}")

        schemas = (spec.get("components") or {}).get("schemas") or {}
        for sp in search_paths:
            post = (paths[sp].get("post") or {})
            body = post.get("requestBody") or {}
            content = (body.get("content") or {})
            ref = None
            for media in content.values():
                ref = ((media.get("schema") or {}).get("$ref"))
                if ref:
                    break
            schema_name = (ref or "").rsplit("/", 1)[-1]
            schema = schemas.get(schema_name) or {}
            required = schema.get("required")
            props = list((schema.get("properties") or {}).keys())
            body_required = body.get("required")
            print(f"  {sp}")
            print(f"    requestBody required (whole body): {body_required}")
            print(f"    schema: {schema_name}")
            print(f"    schema.required   = {required}")
            print(f"    schema.properties = {props}")
            filter_required = bool(required) and any(
                str(x).lower() in {"filtergroups", "filter_groups"} for x in required
            )
            print(f"    >>> vendor requires filterGroups? {filter_required}")
            findings.append(
                {
                    "api": name,
                    "version": version.get("version"),
                    "spec_url": url,
                    "path": sp,
                    "schema": schema_name,
                    "request_body_required": body_required,
                    "schema_required": required,
                    "schema_properties": props,
                    "vendor_requires_filter_groups": filter_required,
                }
            )

    print("\n=== VERDICT ===")
    any_required = [f for f in findings if f["vendor_requires_filter_groups"]]
    if findings and not any_required:
        print("HubSpot's published contract does NOT list filterGroups as required")
        print("on any inspected search endpoint. Our 'requires filter_groups array'")
        print("rule is a Gravitre-side invention, not a vendor constraint.")
    elif any_required:
        print(f"Vendor DOES require filterGroups on: {[f['api'] for f in any_required]}")
    else:
        print("INCONCLUSIVE — no search schema resolved from the published spec.")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "source": "HubSpot published OpenAPI catalog",
                "catalog": CATALOG,
                "findings": findings,
                "vendor_requires_filter_groups_anywhere": bool(any_required),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
