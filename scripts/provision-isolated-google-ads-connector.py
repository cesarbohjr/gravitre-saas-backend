#!/usr/bin/env python3
"""Clone healthy Google Ads OAuth from operator org into isolated smoke org.

Same pattern as provision-isolated-hubspot-slack-connectors.py. SA writes only
into f07e57c0-… . Does not mutate Cesar's operator workspace except read/decrypt
of the source connector secret.

Shares the operator install refresh token (race possible) — isolated smoke only.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import dotenv_values  # noqa: E402

from app.connectors.repository import (  # noqa: E402
    create_connector,
    get_decrypted_secret,
    set_secret,
)
from app.services.conversation_write_guard import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
)

OUT = ROOT / "docs" / "delivery" / "isolated-google-ads-connector-provision.json"
SOURCE_ID = "a726bcae-9710-45fd-bec2-5667c4f22686"
CONNECTOR_TYPE = "google_ads"

CONFIG_ALLOW = {
    "auth_type",
    "customer_id",
    "customerId",
    "login_customer_id",
    "loginCustomerId",
    "customer_name",
    "customerName",
    "oauth_connected_at",
    "oauth_environment",
    "oauth_provider",
    "dataRegion",
}


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (
        ROOT / "backend" / ".env",
        ROOT / "backend" / ".env.operator.local",
        ROOT / ".env",
    ):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update(
                    {k: v for k, v in dotenv_values(path, encoding=enc).items() if v}
                )
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _source_row(client: Any) -> dict[str, Any]:
    rows = (
        client.table("connectors")
        .select("id,type,status,name,config,environment,org_id")
        .eq("id", SOURCE_ID)
        .eq("org_id", FORBIDDEN_OPERATOR_ORG_ID)
        .eq("type", CONNECTOR_TYPE)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise SystemExit("FAIL: source google_ads not in operator org")
    row = dict(rows[0])
    status = str(row.get("status") or "").lower()
    if status not in {"healthy", "active", "connected", "ok"}:
        raise SystemExit(f"FAIL: source google_ads status={row.get('status')!r}")
    return row


def _secret_payloads(client: Any, settings: Any) -> dict[str, str]:
    keys = (
        client.table("connector_secrets")
        .select("key_name")
        .eq("connector_id", SOURCE_ID)
        .execute()
        .data
        or []
    )
    out: dict[str, str] = {}
    for row in keys:
        key_name = str(row.get("key_name") or "").strip()
        if not key_name:
            continue
        plaintext = get_decrypted_secret(client, SOURCE_ID, key_name, settings)
        if plaintext:
            out[key_name] = plaintext
    if "oauth_tokens" not in out:
        raise SystemExit("FAIL: no decryptable oauth_tokens on source google_ads")
    return out


def _clone_config(source: dict[str, Any]) -> dict:
    src_cfg = dict(source.get("config") or {})
    cfg = {k: src_cfg[k] for k in CONFIG_ALLOW if k in src_cfg}
    cfg.update(
        {
            "auth_type": src_cfg.get("auth_type") or "oauth",
            "source": "isolated_google_ads_oauth_clone",
            "cloned_from": SOURCE_ID,
            "operator_org_never_write": FORBIDDEN_OPERATOR_ORG_ID,
            "isolated_smoke": True,
            "oauth_provider": src_cfg.get("oauth_provider") or CONNECTOR_TYPE,
        }
    )
    return cfg


def _ensure_clone(client: Any, settings: Any) -> dict[str, Any]:
    iso = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
    source = _source_row(client)
    secrets = _secret_payloads(client, settings)
    existing = (
        client.table("connectors")
        .select("id,type,status,name,config")
        .eq("org_id", iso)
        .eq("type", CONNECTOR_TYPE)
        .limit(5)
        .execute()
        .data
        or []
    )
    name = "google_ads-isolated-smoke"
    cfg = _clone_config(source)

    if existing:
        row = dict(existing[0])
        cid = str(row["id"])
        for key_name, plaintext in secrets.items():
            set_secret(client, iso, cid, key_name, plaintext, settings)
        client.table("connectors").update(
            {
                "status": "healthy",
                "name": name,
                "config": {**(dict(row.get("config") or {})), **cfg},
                "environment": source.get("environment") or "production",
            }
        ).eq("id", cid).eq("org_id", iso).execute()
        return {
            "action": "refreshed",
            "connector_id": cid,
            "source_connector_id": SOURCE_ID,
            "secret_keys": sorted(secrets.keys()),
            "status": "healthy",
            "customer_id_linked": bool(cfg.get("customer_id") or cfg.get("customerId")),
        }

    created = create_connector(
        client,
        iso,
        CONNECTOR_TYPE,
        cfg,
        DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
        environment_name=str(source.get("environment") or "production"),
        status="healthy",
    )
    cid = str(created["id"])
    for key_name, plaintext in secrets.items():
        set_secret(client, iso, cid, key_name, plaintext, settings)
    client.table("connectors").update(
        {"status": "healthy", "name": name, "vendor": CONNECTOR_TYPE}
    ).eq("id", cid).eq("org_id", iso).execute()
    return {
        "action": "created",
        "connector_id": cid,
        "source_connector_id": SOURCE_ID,
        "secret_keys": sorted(secrets.keys()),
        "status": "healthy",
        "customer_id_linked": bool(cfg.get("customer_id") or cfg.get("customerId")),
    }


def _live_list_proof(client: Any, settings: Any, connector_id: str) -> dict[str, Any]:
    """Read-only Google Ads API call proving the cloned OAuth is live."""
    from app.connectors.google_ads import list_campaigns
    from app.connectors.repository import get_decrypted_secret as _dec
    from app.core.safe_dict import safe_normalize_stored_dict

    row = (
        client.table("connectors")
        .select("id,config,status,org_id")
        .eq("id", connector_id)
        .eq("org_id", DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not row:
        return {"ok": False, "error": "clone row missing"}
    cfg = safe_normalize_stored_dict(row[0], key="config")
    customer_id = str(cfg.get("customer_id") or cfg.get("customerId") or "").strip()
    raw = _dec(client, connector_id, "oauth_tokens", settings) or ""
    try:
        tokens = json.loads(raw) if raw.strip().startswith("{") else {}
    except json.JSONDecodeError:
        tokens = {}
    access = str(tokens.get("access_token") or "").strip()
    developer_token = (getattr(settings, "google_ads_developer_token", None) or "").strip()
    if not access or not developer_token or not customer_id:
        return {
            "ok": False,
            "error": "missing access_token, developer_token, or customer_id",
            "has_access_token": bool(access),
            "has_developer_token": bool(developer_token),
            "has_customer_id": bool(customer_id),
        }
    campaigns = list_campaigns(
        access,
        customer_id,
        developer_token=developer_token,
        limit=5,
    )
    return {
        "ok": True,
        "customer_id_linked": True,
        "campaign_count_sample": len(campaigns or []),
        "sample_names": [
            str(c.get("name") or c.get("campaign") or "")[:80]
            for c in (campaigns or [])[:3]
        ],
    }


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    from app.config import get_settings
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    get_settings.cache_clear()
    settings = get_settings()
    iso = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID

    clone = _ensure_clone(client, settings)
    proof: dict[str, Any] = {"ok": False, "error": "not_run"}
    try:
        proof = _live_list_proof(client, settings, clone["connector_id"])
    except Exception as exc:  # noqa: BLE001
        proof = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:400]}

    report = {
        "isolated_org": iso,
        "operator_org_read_only": FORBIDDEN_OPERATOR_ORG_ID,
        "clone": clone,
        "live_list_proof": proof,
        "developer_token_configured": bool(
            (getattr(settings, "google_ads_developer_token", None) or "").strip()
        ),
        "pass": bool(clone.get("status") == "healthy" and proof.get("ok")),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Disposable Google Ads OAuth clone for isolated typed/spoken smoke; "
            "tokens shared with operator install. Read-only list proof only."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
