"""Does HubSpot itself require filterGroups on an object search, or do we?

Our tool layer refuses hubspot.deals.search without a non-empty filter_groups,
in two places (tool_service and the connector client). Neither refusal comes
from HubSpot. Before relaxing our own validation, ask the real vendor API what
it actually accepts — an unfiltered search either works there or it does not,
and that answer decides whether our rule is a correct guard or an invented one.

Read-only: every request below is a search/read, no writes.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "docs" / "delivery" / "hubspot-search-vendor-contract.json"

CONNECTOR_ID = "41175658-a119-4f3f-949d-0b927e7c0b78"


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    return merged


def main() -> int:
    env = load_env()
    import os

    for k, v in env.items():
        os.environ.setdefault(k, v)

    from supabase import create_client

    from app.config import get_settings
    from app.connectors.hubspot_oauth import ensure_hubspot_access_token

    settings = get_settings()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    conn = (
        sb.table("connectors")
        .select("id,org_id,environment,type")
        .eq("id", CONNECTOR_ID)
        .limit(1)
        .execute()
        .data
    )
    if not conn:
        print(f"connector {CONNECTOR_ID} not found")
        return 2
    org_id = conn[0]["org_id"]
    token, err = ensure_hubspot_access_token(
        sb, org_id, CONNECTOR_ID, settings, environment_name=conn[0].get("environment")
    )
    if err or not token:
        # Local env has no HubSpot OAuth client id/secret, so the refresh path
        # cannot run here. Fall back to the stored access token: if it is still
        # inside its window the vendor answer is just as real.
        print(f"refresh path unavailable ({err}); trying stored access token")
        from app.connectors.hubspot_oauth import load_oauth_tokens

        try:
            stored = load_oauth_tokens(sb, org_id, CONNECTOR_ID) or {}
        except Exception as exc:  # noqa: BLE001
            print(f"could not load stored tokens: {exc}")
            return 2
        token = stored.get("access_token") or stored.get("accessToken")
        print(f"  stored access_token present={bool(token)} expires_at={stored.get('expires_at')}")
        if not token:
            return 2
    print(f"live HubSpot token acquired for connector {CONNECTOR_ID[:8]}… org {str(org_id)[:8]}…")

    props = ["dealname", "dealstage", "amount", "closedate", "pipeline"]
    cases = [
        (
            "search_no_filterGroups_key_at_all",
            {"properties": props, "limit": 5},
        ),
        (
            "search_empty_filterGroups",
            {"filterGroups": [], "properties": props, "limit": 5},
        ),
        (
            "search_empty_filterGroups_with_sort_recent",
            {
                "filterGroups": [],
                "properties": props,
                "limit": 5,
                "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
            },
        ),
    ]

    results = []
    with httpx.Client(timeout=30.0) as client:
        for name, body in cases:
            r = client.post(
                "https://api.hubapi.com/crm/v3/objects/deals/search",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )
            ok = r.status_code < 300
            payload = {}
            try:
                payload = r.json()
            except Exception:  # noqa: BLE001
                payload = {"raw": r.text[:300]}
            n = len(payload.get("results") or []) if isinstance(payload, dict) else 0
            total = payload.get("total") if isinstance(payload, dict) else None
            print(f"\n[{name}]")
            print(f"  HTTP {r.status_code}  vendor_accepts={ok}  returned={n} deal(s) total={total}")
            if not ok:
                print(f"  vendor error: {json.dumps(payload)[:300]}")
            elif n:
                first = (payload["results"][0].get("properties") or {})
                print(f"  sample: {first.get('dealname')!r} amount={first.get('amount')!r} close={first.get('closedate')!r}")
            results.append(
                {
                    "case": name,
                    "request_body": body,
                    "http_status": r.status_code,
                    "vendor_accepts": ok,
                    "returned": n,
                    "total": total,
                    "vendor_error": None if ok else payload,
                }
            )

    accepted = [c for c in results if c["vendor_accepts"]]
    print("\n=== VERDICT ===")
    if accepted:
        print(f"HubSpot ACCEPTS an unfiltered deals search ({len(accepted)}/{len(results)} shapes).")
        print("Our 'requires filter_groups array' rule is invented by us, not the vendor.")
    else:
        print("HubSpot REJECTS every unfiltered shape — our validation mirrors a real vendor rule.")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "connector_id": CONNECTOR_ID,
                "endpoint": "POST /crm/v3/objects/deals/search",
                "cases": results,
                "vendor_accepts_unfiltered": bool(accepted),
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
