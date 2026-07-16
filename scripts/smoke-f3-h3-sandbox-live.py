#!/usr/bin/env python3
"""F3/H3 sandbox-only live tip — Plaid Sandbox + Gusto Demo.

Governance (Cesar 2026-07-16):
  Authorized for Plaid Sandbox + Gusto Demo ONLY — not production/real accounts.
  Evidence MUST record explicit api_base confirmation before any vendor call.

Writes docs/delivery/f3-h3-sandbox-live.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "f3-h3-sandbox-live.json"

PLAID_SANDBOX = "https://sandbox.plaid.com"
GUSTO_DEMO = "https://api.gusto-demo.com/v1"
FORBIDDEN_HOSTS = (
    "production.plaid.com",
    "api.gusto.com",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _refuse_if_production(api_base: str, label: str) -> None:
    lower = api_base.lower()
    for bad in FORBIDDEN_HOSTS:
        if bad in lower:
            raise SystemExit(
                f"REFUSED: {label} api_base={api_base} points at production host {bad}. "
                "F3/H3 authorization is sandbox/demo only."
            )


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.connectors.repository import get_connector_by_type, get_decrypted_secret
    from app.services.gusto_tools import resolve_gusto_api_base
    from app.services.plaid_tools import resolve_plaid_api_base
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    # Force sandbox/demo for this tip regardless of ambient env.
    settings.plaid_env = "sandbox"
    settings.gusto_env = "demo"

    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")

    plaid_base, plaid_env = resolve_plaid_api_base(settings=settings, params={"plaid_env": "sandbox"})
    gusto_base, gusto_env = resolve_gusto_api_base(settings=settings, params={"gusto_env": "demo"})
    _refuse_if_production(plaid_base, "Plaid")
    _refuse_if_production(gusto_base, "Gusto")

    endpoint_confirmation = {
        "plaid_env": plaid_env,
        "plaid_api_base": plaid_base,
        "plaid_is_sandbox": plaid_base.rstrip("/") == PLAID_SANDBOX,
        "gusto_env": gusto_env,
        "gusto_api_base": gusto_base,
        "gusto_is_demo": gusto_base.rstrip("/") == GUSTO_DEMO,
        "production_hosts_refused": list(FORBIDDEN_HOSTS),
        "authorized_scope": "sandbox_demo_live_invoke_only",
        "not_authorized": "production_real_account_activation",
    }
    if not endpoint_confirmation["plaid_is_sandbox"] or not endpoint_confirmation["gusto_is_demo"]:
        raise SystemExit(f"Endpoint confirmation failed: {endpoint_confirmation}")

    def _any_connector(vendor: str) -> dict | None:
        # Active-only helper first; fall back to any row so staged pack scaffolds surface.
        active = get_connector_by_type(sb, ORG, vendor, environment_name="production")
        if active:
            return active
        rows = (
            sb.table("connectors")
            .select("id,type,status,environment,config")
            .eq("org_id", ORG)
            .eq("type", vendor)
            .limit(5)
            .execute()
        )
        return (rows.data or [None])[0]

    plaid_conn = _any_connector("plaid")
    gusto_conn = _any_connector("gusto")

    plaid_result: dict = {
        "connector_id": str(plaid_conn["id"]) if plaid_conn else None,
        "connector_status": (plaid_conn or {}).get("status"),
    }
    gusto_result: dict = {
        "connector_id": str(gusto_conn["id"]) if gusto_conn else None,
        "connector_status": (gusto_conn or {}).get("status"),
    }

    # --- Plaid Sandbox ---
    if plaid_conn:
        cid = str(plaid_conn["id"])
        access = get_decrypted_secret(sb, cid, "access_token", settings) or get_decrypted_secret(
            sb, cid, "plaid_access_token", settings
        )
        client_id = get_decrypted_secret(sb, cid, "client_id", settings) or settings.plaid_client_id
        secret = get_decrypted_secret(sb, cid, "secret", settings) or settings.plaid_secret

        if not access and client_id and secret:
            # Create a disposable sandbox Item (First Platypus Bank) then exchange.
            _refuse_if_production(plaid_base, "Plaid sandbox/public_token/create")
            create_body = {
                "client_id": client_id,
                "secret": secret,
                "institution_id": "ins_109508",
                "initial_products": ["transactions"],
                "options": {"override_username": "user_good", "override_password": "pass_good"},
            }
            with httpx.Client(timeout=60.0) as http:
                created = http.post(f"{plaid_base}/sandbox/public_token/create", json=create_body)
            plaid_result["sandbox_public_token_create_status"] = created.status_code
            if created.status_code < 400:
                public_token = (created.json() or {}).get("public_token")
                exch = httpx.post(
                    f"{plaid_base}/item/public_token/exchange",
                    json={"client_id": client_id, "secret": secret, "public_token": public_token},
                    timeout=60.0,
                )
                plaid_result["sandbox_exchange_status"] = exch.status_code
                if exch.status_code < 400:
                    access = (exch.json() or {}).get("access_token")
                    # Persist temporarily onto connector for invoke_tool path.
                    from app.connectors.repository import set_secret

                    set_secret(sb, ORG, cid, "access_token", access, settings)
                    plaid_result["sandbox_item_created"] = True

        if access:
            ctx = ToolContext(
                settings=settings,
                client=sb,
                org_id=ORG,
                actor_id=ACTOR,
                connector_id=cid,
            )
            got = invoke_tool(
                ctx,
                "plaid.accounts.get",
                {"connector_id": cid, "plaid_env": "sandbox"},
            )
            data = got.data or {}
            used_base = str(data.get("api_base") or "")
            _refuse_if_production(used_base or plaid_base, "Plaid accounts.get result")
            plaid_result.update(
                {
                    "action": "plaid.accounts.get",
                    "success": got.success,
                    "error_code": got.error_code,
                    "error_message": got.error_message,
                    "api_base": used_base or plaid_base,
                    "plaid_env": data.get("plaid_env") or "sandbox",
                    "account_count": len(data.get("accounts") or [])
                    if isinstance(data.get("accounts"), list)
                    else None,
                }
            )
        else:
            plaid_result.update(
                {
                    "success": False,
                    "status": "BLOCKED_EXTERNAL",
                    "error": (
                        "Plaid connector is staged (needs_connection) and no sandbox "
                        "PLAID_CLIENT_ID/PLAID_SECRET available to create a sandbox Item. "
                        "Connect Plaid Link against Sandbox or set sandbox credentials."
                    ),
                    "api_base_confirmed": plaid_base,
                }
            )
    else:
        plaid_result.update(
            {
                "success": False,
                "status": "BLOCKED_EXTERNAL",
                "error": "No Plaid connector row on smoke org",
                "api_base_confirmed": plaid_base,
            }
        )

    # --- Gusto Demo ---
    if gusto_conn:
        cid = str(gusto_conn["id"])
        token = (
            get_decrypted_secret(sb, cid, "access_token", settings)
            or get_decrypted_secret(sb, cid, "oauth_access_token", settings)
            or get_decrypted_secret(sb, cid, "api_token", settings)
        )
        if token:
            ctx = ToolContext(
                settings=settings,
                client=sb,
                org_id=ORG,
                actor_id=ACTOR,
                connector_id=cid,
            )
            got = invoke_tool(
                ctx,
                "gusto.companies.get",
                {"connector_id": cid, "gusto_env": "demo"},
            )
            data = got.data or {}
            used_base = str(data.get("api_base") or "")
            _refuse_if_production(used_base or gusto_base, "Gusto companies.get result")
            gusto_result.update(
                {
                    "action": "gusto.companies.get",
                    "success": got.success,
                    "error_code": got.error_code,
                    "error_message": got.error_message,
                    "api_base": used_base or gusto_base,
                    "gusto_env": data.get("gusto_env") or "demo",
                    "summary": data.get("summary"),
                }
            )
        else:
            gusto_result.update(
                {
                    "success": False,
                    "status": "BLOCKED_EXTERNAL",
                    "error": (
                        "Gusto connector is staged (needs_connection) with no OAuth token. "
                        "Connect via Gusto Demo OAuth (api.gusto-demo.com) then re-run."
                    ),
                    "api_base_confirmed": gusto_base,
                    "oauth_authorize_confirmed": "https://api.gusto-demo.com/oauth/authorize",
                }
            )
    else:
        gusto_result.update(
            {
                "success": False,
                "status": "BLOCKED_EXTERNAL",
                "error": "No Gusto connector row on smoke org",
                "api_base_confirmed": gusto_base,
            }
        )

    plaid_ok = bool(plaid_result.get("success"))
    gusto_ok = bool(gusto_result.get("success"))
    artifact = {
        "pass": plaid_ok and gusto_ok,
        "status": (
            "PASS"
            if plaid_ok and gusto_ok
            else "PARTIAL"
            if plaid_ok or gusto_ok
            else "BLOCKED_EXTERNAL"
        ),
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "f3-h3-sandbox-demo-live",
        "endpoint_confirmation": endpoint_confirmation,
        "governance": {
            "authorized": "plaid_sandbox_and_gusto_demo_live_invoke",
            "not_authorized": "production_real_account_activation",
            "signoff": "Cesar 2026-07-16 F3/H3 sandbox synthetic confirmation",
        },
        "plaid": plaid_result,
        "gusto": gusto_result,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
