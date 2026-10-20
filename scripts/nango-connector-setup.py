#!/usr/bin/env python3
"""Audit/provision exact Nango templates. Never update existing apps or credentials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.connectors.nango_registry import NANGO_CONNECTOR_REGISTRY, NANGO_FALLBACK_REGISTRY


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create missing integration configurations only")
    parser.add_argument("--vendor", help="Limit the audit to one vendor")
    parser.add_argument("--output", type=Path, required=True, help="Safe metadata report; no provider/user credentials")
    args = parser.parse_args()
    key = os.environ.get("NANGO_SECRET_KEY", "").strip()
    if not key:
        parser.error("NANGO_SECRET_KEY is required")
    base = os.environ.get("NANGO_API_BASE_URL", "https://api.nango.dev").rstrip("/")
    rows = []
    with httpx.Client(base_url=base, headers={"Authorization": f"Bearer {key}"}, timeout=30) as client:
        providers_response = client.get("/providers"); providers_response.raise_for_status()
        providers = {p["name"]: p for p in providers_response.json()["data"]}
        inventory_response = client.get("/integrations"); inventory_response.raise_for_status()
        inventory = {r["unique_key"]: r for r in inventory_response.json()["data"]}
        specs = (*NANGO_CONNECTOR_REGISTRY.values(), *NANGO_FALLBACK_REGISTRY.values())
        for spec in specs:
            if args.vendor and args.vendor != spec.vendor:
                continue
            item = {"vendor": spec.vendor, "integration_id": spec.integration_id, "provider": spec.provider,
                    "native_fallback": spec.native_fallback, "created": False}
            if spec.provider not in providers:
                item["state"] = "provider_not_supported"
            else:
                integration = inventory.get(spec.integration_id)
                if integration is None and args.apply:
                    response = client.post("/integrations", json={"unique_key": spec.integration_id,
                                                                  "provider": spec.provider, "display_name": spec.display_name})
                    if response.status_code not in {200, 201}:
                        item.update(state="creation_failed", http_status=response.status_code)
                        rows.append(item)
                        print(json.dumps(item), flush=True)
                        if response.status_code in {401, 403, 429}:
                            break
                        continue
                    integration = response.json().get("data", {})
                    item["created"] = True
                if integration is None:
                    item["state"] = "integration_missing"
                elif integration.get("provider") != spec.provider:
                    item["state"] = "provider_mismatch"
                else:
                    missing = integration.get("missing_fields")
                    item["state"] = "ready_for_account_authorization" if missing == [] else "provider_credentials_required"
                    item["missing_fields"] = missing
                    item["auth_mode"] = providers[spec.provider].get("auth_mode")
            rows.append(item)
            args.output.write_text(json.dumps(rows, indent=2) + "\n")
            print(json.dumps(item), flush=True)
    args.output.write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    run()
