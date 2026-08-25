#!/usr/bin/env python3
"""Patch operator Clay connector webhook_url to a real table ingest URL.

Usage (after Supabase is restored):
  set CLAY_TABLE_WEBHOOK_URL=https://app.clay.com/api/v1/webhooks/...
  python scripts/patch-clay-connector-webhook.py

Reads connector 17a942d4… for org cbbf993b… by default.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = os.environ.get("SMOKE_ORG_ID", "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea")
CLAY_ID = os.environ.get("CLAY_CONNECTOR_ID", "17a942d4-d5cf-44da-9ad2-c0bdb4faf729")


def load_env() -> None:
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                for k, v in (loaded or {}).items():
                    if v:
                        os.environ.setdefault(k, v)
                break
            except UnicodeDecodeError:
                continue


def validate_webhook(url: str) -> str:
    url = url.strip()
    if not url:
        raise SystemExit("CLAY_TABLE_WEBHOOK_URL is empty")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SystemExit(f"Invalid webhook scheme: {parsed.scheme}")
    lowered = url.lower()
    if "/shared-workbook/" in lowered or "/share_" in lowered:
        raise SystemExit(
            "URL looks like a Clay shared-workbook page (GET-only). "
            "Use the table HTTP API / webhook ingest URL from Clay."
        )
    if "webhooks" not in lowered and "webhook" not in lowered:
        print("warning: URL does not contain 'webhook' — confirm this is the ingest endpoint")
    return url


def main() -> int:
    load_env()
    new_url = validate_webhook(os.environ.get("CLAY_TABLE_WEBHOOK_URL", ""))

    from app.config import get_settings
    from app.core.safe_dict import safe_normalize_stored_dict
    from supabase import create_client

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    row = (
        sb.table("connectors")
        .select("id, org_id, name, webhook_url, config")
        .eq("id", CLAY_ID)
        .eq("org_id", ORG)
        .limit(1)
        .execute()
    ).data or []
    if not row:
        raise SystemExit(f"Clay connector {CLAY_ID} not found for org {ORG}")

    before = row[0]
    cfg = safe_normalize_stored_dict(before, key="config")
    cfg["webhook_url"] = new_url
    cfg["webhookUrl"] = new_url

    sb.table("connectors").update({"webhook_url": new_url, "config": cfg}).eq("id", CLAY_ID).execute()
    after = (
        sb.table("connectors")
        .select("id, webhook_url, config")
        .eq("id", CLAY_ID)
        .limit(1)
        .execute()
    ).data[0]

    print("patched", CLAY_ID)
    print("before_host", urlparse(str(before.get("webhook_url") or "")).netloc)
    print("after_host", urlparse(str(after.get("webhook_url") or "")).netloc)
    print("next: HUBSPOT_LIST_ID=48 python scripts/live-msp-clay-hubspot-asyncio-fix.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
