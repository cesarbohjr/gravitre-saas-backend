#!/usr/bin/env python3
"""Clone healthy HubSpot + Slack OAuth from operator org into isolated smoke org.

Disposable test fixture for STA-305 live. SA writes only into f07e57c0-…
(Module 0 allow-list). Does not mutate Cesar's operator workspace rows except
read/decrypt of source connector secrets.

Shares the same OAuth install tokens as the operator workspace (refresh races
possible) — acceptable for isolated smoke only.
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

OUT = ROOT / "docs" / "delivery" / "isolated-hubspot-slack-connector-provision.json"

# Healthy production connectors in operator workspace (verified 2026-07-23).
SOURCES: dict[str, str] = {
    "hubspot": "547cdda5-2637-4a2b-b087-d5ea89486575",
    "slack": "fe7433c3-6475-474a-863f-91b98d17a0b8",
}

# Config keys safe to mirror for smoke auth/metadata (skip org-bound sync/RAG/triggers).
CONFIG_ALLOW = {
    "auth_type",
    "dataRegion",
    "hub_domain",
    "hub_id",
    "oauth_connected_at",
    "oauth_environment",
    "oauth_provider",
    "oauth_reconnected_at",
    "slack_app_id",
    "slack_bot_user_id",
    "slack_team_id",
    "slack_team_name",
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


def _source_row(client: Any, connector_type: str, source_id: str) -> dict[str, Any]:
    rows = (
        client.table("connectors")
        .select("id,type,status,name,config,environment,org_id")
        .eq("id", source_id)
        .eq("org_id", FORBIDDEN_OPERATOR_ORG_ID)
        .eq("type", connector_type)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise SystemExit(
            f"FAIL: source {connector_type} {source_id} not in operator org"
        )
    row = dict(rows[0])
    status = str(row.get("status") or "").lower()
    if status not in {"healthy", "active", "connected", "ok"}:
        raise SystemExit(
            f"FAIL: source {connector_type} status={row.get('status')!r} not healthy"
        )
    return row


def _secret_payloads(
    client: Any, source_id: str, settings: Any
) -> dict[str, str]:
    keys = (
        client.table("connector_secrets")
        .select("key_name")
        .eq("connector_id", source_id)
        .execute()
        .data
        or []
    )
    out: dict[str, str] = {}
    for row in keys:
        key_name = str(row.get("key_name") or "").strip()
        if not key_name:
            continue
        plaintext = get_decrypted_secret(client, source_id, key_name, settings)
        if plaintext:
            out[key_name] = plaintext
    if "oauth_tokens" not in out:
        raise SystemExit(f"FAIL: no decryptable oauth_tokens on {source_id}")
    return out


def _clone_config(source: dict[str, Any], *, connector_type: str, source_id: str) -> dict:
    src_cfg = dict(source.get("config") or {})
    cfg = {k: src_cfg[k] for k in CONFIG_ALLOW if k in src_cfg}
    cfg.update(
        {
            "auth_type": src_cfg.get("auth_type") or "oauth",
            "source": "sta305_isolated_oauth_clone",
            "cloned_from": source_id,
            "operator_org_never_write": FORBIDDEN_OPERATOR_ORG_ID,
            "isolated_smoke": True,
            "oauth_provider": src_cfg.get("oauth_provider") or connector_type,
        }
    )
    return cfg


def _ensure_clone(
    client: Any,
    settings: Any,
    *,
    connector_type: str,
    source_id: str,
) -> dict[str, Any]:
    iso = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
    source = _source_row(client, connector_type, source_id)
    secrets = _secret_payloads(client, source_id, settings)
    existing = (
        client.table("connectors")
        .select("id,type,status,name,config")
        .eq("org_id", iso)
        .eq("type", connector_type)
        .limit(5)
        .execute()
        .data
        or []
    )
    name = f"{connector_type}-isolated-smoke"
    cfg = _clone_config(source, connector_type=connector_type, source_id=source_id)

    if existing:
        row = dict(existing[0])
        cid = str(row["id"])
        # Refresh secrets + mark healthy (token may have rotated on operator side).
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
            "type": connector_type,
            "connector_id": cid,
            "source_connector_id": source_id,
            "secret_keys": sorted(secrets.keys()),
            "status": "healthy",
        }

    created = create_connector(
        client,
        iso,
        connector_type,
        cfg,
        DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
        environment_name=str(source.get("environment") or "production"),
        status="healthy",
    )
    cid = str(created["id"])
    for key_name, plaintext in secrets.items():
        set_secret(client, iso, cid, key_name, plaintext, settings)
    client.table("connectors").update(
        {"status": "healthy", "name": name, "vendor": connector_type}
    ).eq("id", cid).eq("org_id", iso).execute()
    return {
        "action": "created",
        "type": connector_type,
        "connector_id": cid,
        "source_connector_id": source_id,
        "secret_keys": sorted(secrets.keys()),
        "status": "healthy",
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

    results = []
    for connector_type, source_id in SOURCES.items():
        results.append(
            _ensure_clone(
                client, settings, connector_type=connector_type, source_id=source_id
            )
        )

    # Post-check: isolated org must show both healthy.
    rows = (
        client.table("connectors")
        .select("type,status,name")
        .eq("org_id", iso)
        .in_("type", ["hubspot", "slack", "apollo"])
        .execute()
        .data
        or []
    )
    connected = sorted(
        {
            str(r["type"])
            for r in rows
            if str(r.get("status") or "").lower()
            in {"healthy", "active", "connected", "ok"}
        }
    )
    report = {
        "isolated_org": iso,
        "operator_org_read_only": FORBIDDEN_OPERATOR_ORG_ID,
        "clones": results,
        "connected_integrations": connected,
        "required": ["hubspot", "slack"],
        "pass": all(c in connected for c in ("hubspot", "slack")),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Disposable HubSpot+Slack OAuth clones for STA-305 live in isolated org; "
            "tokens shared with operator install"
        ),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
