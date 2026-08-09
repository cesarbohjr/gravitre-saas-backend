#!/usr/bin/env python3
"""Live prove: scaffolding Meson SKUs are archived and hidden from customer API."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import jwt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
for candidate in [ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"]:
    if not candidate.exists():
        continue
    for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

from supabase import create_client  # noqa: E402
from app.config import get_settings  # noqa: E402

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
UID = "f7e32f06-49df-4e73-8962-f41c21850762"
API = (os.environ.get("API_PUBLIC_URL") or "https://api.gravitre.app").rstrip("/")
FORBIDDEN = {
    "multi_language",
    "advanced_analytics",
    "compliance_pack",
    "custom_model_training",
    "voice_interface",
}
OUT = ROOT / "docs" / "delivery" / "meson-scaffolding-addons-archived-live.json"


def _token() -> str:
    s = get_settings()
    c = create_client(s.supabase_url, s.supabase_service_role_key)
    email = (c.auth.admin.get_user_by_id(UID).user.email) or f"{UID}@gravitre.local"
    now = int(time.time())
    t = jwt.encode(
        {
            "sub": UID,
            "email": email,
            "aud": "authenticated",
            "iss": f"{s.supabase_url.rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        s.supabase_jwt_secret,
        algorithm="HS256",
    )
    return t.decode() if isinstance(t, bytes) else t


def _get(path: str, token: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "x-org-id": ORG,
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def main() -> int:
    s = get_settings()
    client = create_client(s.supabase_url, s.supabase_service_role_key)
    health_code, health = _get("/health", _token())
    tip = str(health.get("git_sha") or "")

    catalog = (
        client.table("meson_addon_catalog")
        .select("code, monthly_price_usd, stripe_price_id, archived_at, name")
        .in_("code", list(FORBIDDEN))
        .execute()
        .data
        or []
    )
    by_code = {str(r.get("code")): r for r in catalog}
    archived_ok = all(
        by_code.get(code) and by_code[code].get("archived_at") is not None for code in FORBIDDEN
    )

    # Any org still carrying scaffolding flags?
    dirty = (
        client.table("subscriptions")
        .select("org_id, meson_addons")
        .not_.is_("meson_addons", "null")
        .execute()
        .data
        or []
    )
    dirty_orgs = []
    for row in dirty:
        addons = row.get("meson_addons") or []
        if isinstance(addons, list) and any(str(a) in FORBIDDEN for a in addons):
            dirty_orgs.append(str(row.get("org_id")))

    code, body = _get("/api/settings/meson-addons", _token())
    api_codes = [str(a.get("code")) for a in (body.get("addons") or [])]
    leaked = sorted(FORBIDDEN.intersection(api_codes))
    total = float(body.get("monthly_total_usd") or 0)
    pass_live = (
        health_code == 200
        and code == 200
        and archived_ok
        and not leaked
        and total == 0.0
        and len(dirty_orgs) == 0
        and (body.get("addon_audit") or {}).get("scaffolding_skus") == "archived_hidden"
    )
    evidence = {
        "at": datetime.now(timezone.utc).isoformat(),
        "api": API,
        "health_git_sha": tip,
        "meson_addons_http": code,
        "api_addon_codes": api_codes,
        "leaked_scaffolding_codes": leaked,
        "monthly_total_usd": total,
        "catalog_archived": {
            code: {
                "archived_at": (by_code.get(code) or {}).get("archived_at"),
                "monthly_price_usd": (by_code.get(code) or {}).get("monthly_price_usd"),
                "name": (by_code.get(code) or {}).get("name"),
            }
            for code in sorted(FORBIDDEN)
        },
        "orgs_with_scaffolding_flags": dirty_orgs,
        "addon_audit": body.get("addon_audit"),
        "pass": pass_live,
    }
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if pass_live else 1


if __name__ == "__main__":
    raise SystemExit(main())
