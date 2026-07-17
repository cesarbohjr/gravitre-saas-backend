#!/usr/bin/env python3
"""Upsert smoke-org AI Search BYO connectors (Ahrefs / Finseo / optional UI).

Usage (PowerShell):
  $env:AHREFS_API_KEY = '<key>'   # or AHREFS_API_TOKEN
  $env:FINSEO_API_KEY = '<key>'
  python scripts/upsert-smoke-ai-search-byo-connectors.py

Never commit keys. Activates stubs and stores org secrets only.
UI connector can activate without a key (surfaces.list is local allowlist).
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


def _upsert(
    sb,
    *,
    connector_type: str,
    api_key: str | None,
    dashboard_url: str,
    label: str,
    require_key: bool,
    settings,
) -> dict:
    from app.connectors.platform import store_connector_api_key
    from app.connectors.repository import create_connector, get_connector_by_type
    from app.intelligence_packs.shared.auth_mode import get_auth_mode

    auth_mode = get_auth_mode(connector_type).value
    existing = get_connector_by_type(sb, ORG, connector_type, environment_name="production")
    # Also pick up needs_connection stubs (get_connector_by_type only returns usable).
    if not existing:
        staged = (
            sb.table("connectors")
            .select("id, type, status, config")
            .eq("org_id", ORG)
            .eq("type", connector_type)
            .is_("deleted_at", "null")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        ).data
        existing = staged[0] if staged else None

    config = {
        **(existing.get("config") if existing else {}),
        "auth_mode": auth_mode,
        "byo": True,
        "dashboard_url": dashboard_url,
        "label": label,
    }

    if existing:
        cid = str(existing["id"])
        sb.table("connectors").update({"status": "active", "config": config}).eq("id", cid).eq(
            "org_id", ORG
        ).execute()
    else:
        if require_key and not api_key:
            return {"ok": False, "type": connector_type, "error": "missing_api_key"}
        row = create_connector(
            sb,
            ORG,
            connector_type,
            config,
            created_by=ACTOR,
            environment_name="production",
            status="active",
        )
        cid = str(row["id"])

    key_stored = False
    key_prefix = None
    if api_key:
        store_connector_api_key(sb, ORG, cid, api_key, settings)
        key_stored = True
        key_prefix = api_key[:4] + "…"
    elif require_key:
        return {"ok": False, "type": connector_type, "connector_id": cid, "error": "missing_api_key"}

    return {
        "ok": True,
        "type": connector_type,
        "connector_id": cid,
        "auth_mode": auth_mode,
        "key_stored": key_stored,
        "key_prefix": key_prefix,
        "dashboard_url": dashboard_url,
    }


def main() -> int:
    _load_env()
    from app.config import get_settings

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)

    ahrefs_key = (
        os.environ.get("AHREFS_API_KEY") or os.environ.get("AHREFS_API_TOKEN") or ""
    ).strip()
    finseo_key = (os.environ.get("FINSEO_API_KEY") or "").strip()
    ui_key = (os.environ.get("AI_VISIBILITY_UI_API_KEY") or "").strip() or None

    results = [
        _upsert(
            sb,
            connector_type="ahrefs",
            api_key=ahrefs_key or None,
            dashboard_url="https://app.ahrefs.com/",
            label="Ahrefs (BYO)",
            require_key=True,
            settings=settings,
        ),
        _upsert(
            sb,
            connector_type="finseo",
            api_key=finseo_key or None,
            dashboard_url="https://app.finseo.ai/",
            label="Finseo (BYO)",
            require_key=True,
            settings=settings,
        ),
        _upsert(
            sb,
            connector_type="ai_visibility_ui",
            api_key=ui_key,
            dashboard_url="https://gravitre.app/connectors?type=ai_visibility_ui",
            label="AI Visibility UI (S2)",
            require_key=False,
            settings=settings,
        ),
    ]
    out = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "org_id": ORG,
        "results": results,
        "ok": any(r.get("ok") and r.get("type") in {"ahrefs", "finseo"} for r in results)
        or any(r.get("ok") and r.get("type") == "ai_visibility_ui" for r in results),
    }
    print(json.dumps(out, indent=2))
    # Exit 0 if at least one API BYO connected OR UI activated
    api_ok = any(r.get("ok") and r.get("key_stored") for r in results if r.get("type") in {"ahrefs", "finseo"})
    ui_ok = any(r.get("ok") and r.get("type") == "ai_visibility_ui" for r in results)
    return 0 if (api_ok or ui_ok) else 2


if __name__ == "__main__":
    raise SystemExit(main())
