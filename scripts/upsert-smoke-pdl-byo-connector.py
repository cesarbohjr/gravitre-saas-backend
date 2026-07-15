#!/usr/bin/env python3
"""Upsert smoke-org People Data Labs BYO connector (API key from env only).

Usage (PowerShell):
  $env:PDL_API_KEY = '<key>'
  python scripts/upsert-smoke-pdl-byo-connector.py

Never commit the key. Reads SUPABASE_* from primary checkout .env when run from a worktree.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"


def _load_env() -> None:
    candidates = [
        BACKEND / ".env",
        BACKEND / ".env.operator.local",
        REPO / ".env",
    ]
    if REPO.parent.name == ".cursor-tmp":
        primary = REPO.parent.parent
        candidates.extend(
            [
                primary / "backend" / ".env",
                primary / "backend" / ".env.operator.local",
                primary / ".env",
            ]
        )
    merged: dict[str, str] = {}
    for p in candidates:
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in (loaded or {}).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    api_key = (os.environ.get("PDL_API_KEY") or "").strip()
    if not api_key:
        print(json.dumps({"ok": False, "error": "Set PDL_API_KEY in the environment"}))
        return 2

    from app.config import get_settings
    from app.connectors.platform import store_connector_api_key
    from app.connectors.repository import create_connector, get_connector_by_type
    from app.intelligence_packs.shared.auth_mode import get_auth_mode

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    existing = get_connector_by_type(sb, ORG, "pdl", environment_name="production")
    if existing:
        cid = str(existing["id"])
        # Ensure active + BYO auth_mode stamp
        sb.table("connectors").update(
            {
                "status": "active",
                "config": {
                    **(existing.get("config") or {}),
                    "auth_mode": get_auth_mode("pdl").value,
                    "byo": True,
                    "dashboard_url": "https://dashboard.peopledatalabs.com/",
                },
            }
        ).eq("id", cid).eq("org_id", ORG).execute()
    else:
        row = create_connector(
            sb,
            ORG,
            "pdl",
            {
                "auth_mode": get_auth_mode("pdl").value,
                "byo": True,
                "dashboard_url": "https://dashboard.peopledatalabs.com/",
                "label": "People Data Labs (BYO)",
            },
            created_by=ACTOR,
            environment_name="production",
            status="active",
        )
        cid = str(row["id"])

    store_connector_api_key(sb, ORG, cid, api_key, settings)
    out = {
        "ok": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "org_id": ORG,
        "connector_id": cid,
        "auth_mode": get_auth_mode("pdl").value,
        "dashboard_url": "https://dashboard.peopledatalabs.com/",
        "key_stored": True,
        "key_prefix": api_key[:4] + "…",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
