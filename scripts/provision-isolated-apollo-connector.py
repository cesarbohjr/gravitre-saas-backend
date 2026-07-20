#!/usr/bin/env python3
"""Clone healthy Apollo API key from operator org into the isolated smoke org.

Disposable test fixture for Phase 0.4 real-vendor success — SA writes only into
f07e57c0-… (Module 0 allow-list). Does not touch Cesar's operator workspace rows
except read/decrypt of the source connector secret.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

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

OUT = ROOT / "docs" / "delivery" / "isolated-apollo-connector-provision.json"
SOURCE_APOLLO_ID = "30f734a2-dbdb-45aa-9112-19c6d604d451"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ROOT / "backend" / ".env", ROOT / "backend" / ".env.operator.local", ROOT / ".env"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(path, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


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
    # Reuse existing isolated apollo if present.
    existing = (
        client.table("connectors")
        .select("id,type,status,name")
        .eq("org_id", iso)
        .eq("type", "apollo")
        .limit(5)
        .execute()
        .data
        or []
    )
    if existing:
        report = {
            "action": "reuse",
            "isolated_org": iso,
            "connector": existing[0],
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0

    secret_key = None
    plaintext = None
    for key_name in ("api_token", "api_key", "oauth_tokens", "APOLLO_API_KEY"):
        plaintext = get_decrypted_secret(client, SOURCE_APOLLO_ID, key_name, settings)
        if plaintext:
            secret_key = key_name
            break
    if not plaintext or not secret_key:
        secrets = (
            client.table("connector_secrets")
            .select("key_name")
            .eq("connector_id", SOURCE_APOLLO_ID)
            .execute()
            .data
            or []
        )
        print("FAIL: no decryptable apollo secret; keys=", [s.get("key_name") for s in secrets])
        return 1

    created = create_connector(
        client,
        iso,
        "apollo",
        {
            "name": "apollo-isolated-smoke",
            "source": "phase0_real_vendor_clone",
            "cloned_from": SOURCE_APOLLO_ID,
            "operator_org_never_write": FORBIDDEN_OPERATOR_ORG_ID,
            "auth": "oauth" if secret_key == "oauth_tokens" else "api_key",
        },
        DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
        environment_name="production",
        status="healthy",
    )
    set_secret(client, iso, str(created["id"]), secret_key, plaintext, settings)
    # Prefer healthy/active status for execution_available
    client.table("connectors").update(
        {"status": "healthy", "name": "apollo-isolated-smoke"}
    ).eq("id", created["id"]).eq("org_id", iso).execute()

    report = {
        "action": "created",
        "isolated_org": iso,
        "connector_id": created["id"],
        "source_connector_id": SOURCE_APOLLO_ID,
        "secret_key": secret_key,
        "status": "healthy",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "note": "Disposable Apollo in isolated org for Module A success fanout proofs",
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
