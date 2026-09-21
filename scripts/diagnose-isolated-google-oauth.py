"""Diagnose isolated-org Google OAuth without printing secrets.

Reports whether a refresh token exists (boolean only), expiry, and whether
interactive reconnect is required. Never logs tokens.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    resolve_isolated_conversation_actor,
)


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k, v in merged.items():
        if v and not os.environ.get(k):
            os.environ[k] = v
    return merged


def main() -> int:
    env = load_env()
    from supabase import create_client

    from app.config import get_settings
    from app.connectors.hubspot_oauth import load_oauth_tokens, token_needs_refresh
    from app.connectors.repository import list_connectors
    from app.services.conversation_write_guard import isolated_conversation_test_org_id

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, _user, _email = resolve_isolated_conversation_actor(env, sb)
    if org_id == FORBIDDEN_OPERATOR_ORG_ID:
        raise SystemExit("refusing operator org")
    settings = get_settings()
    print(f"org={org_id} isolated={org_id == isolated_conversation_test_org_id()}")
    for row in list_connectors(sb, org_id, "production"):
        vendor = str(row.get("type") or row.get("vendor") or "")
        if vendor not in {"google_analytics", "google_search_console", "gmail"}:
            continue
        connector_id = str(row.get("id") or "")
        tokens = load_oauth_tokens(sb, connector_id, settings) or {}
        print(
            {
                "vendor": vendor,
                "status": row.get("status"),
                "has_access_token": bool(tokens.get("access_token")),
                "has_refresh_token": bool(tokens.get("refresh_token")),
                "needs_refresh": token_needs_refresh(tokens, 300) if tokens else True,
                "reconnect_path": f"/connectors -> {vendor} -> Connect (isolated org only)",
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
