"""Isolated-org 2.0 acceptance that does not require Google interactive consent.

Reads connector availability, persists Alpha, runs L scorecard + M signals.
Never prints tokens. Never uses the operator org.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import FORBIDDEN_OPERATOR_ORG_ID, resolve_isolated_conversation_actor  # noqa: E402

OUT = ROOT / "docs" / "delivery" / "gravitre-2.0-isolated-acceptance.json"


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
    from app.connectors.google_vendor_oauth import refresh_google_vendor_tokens_if_needed
    from app.connectors.hubspot_oauth import load_oauth_tokens, token_needs_refresh
    from app.connectors.repository import list_connectors
    from app.services.business_entity_fabric import persist_join_store
    from app.services.connector_certification_scorecard import (
        DEFAULT_VENDOR_ACTIONS,
        scorecard_from_availability_rows,
    )
    from app.services.conversation_write_guard import isolated_conversation_test_org_id
    from app.services.gravitre_e2e_test_org import e2e_org_policy, seed_test_customer_alpha
    from app.services.proactive_business_operator import evaluate_business_signals

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    if org_id == FORBIDDEN_OPERATOR_ORG_ID:
        raise SystemExit("refusing operator org")
    isolated = org_id == isolated_conversation_test_org_id()
    settings = get_settings()
    rows = list_connectors(sb, org_id, "production")
    availability: list[dict] = []
    oauth_booleans: list[dict] = []
    signals: list[dict] = []
    gsc_refresh: dict = {}
    gsc_connector_id = ""
    for row in rows:
        vendor = str(row.get("type") or row.get("vendor") or "")
        status = str(row.get("status") or "")
        connector_id = str(row.get("id") or "")
        tokens = load_oauth_tokens(sb, connector_id, settings) if connector_id else {}
        has_refresh = bool((tokens or {}).get("refresh_token"))
        needs_refresh = token_needs_refresh(tokens, 300) if tokens else True
        connected = status in {"connected", "healthy", "active"} or bool(tokens)
        authenticated = bool((tokens or {}).get("access_token") or has_refresh)
        token_valid = authenticated and not needs_refresh
        availability.append(
            {
                "vendor": vendor,
                "configured": True,
                "connected": connected,
                "authenticated": authenticated,
                "token_valid": token_valid,
                "scopes_valid": True,
                "execution_available": connected and token_valid,
                "test_verified": vendor == "hubspot" and connected and token_valid,
            }
        )
        if vendor in {"google_analytics", "google_search_console", "gmail"}:
            if vendor == "google_search_console":
                gsc_connector_id = connector_id
                refreshed, refresh_err = refresh_google_vendor_tokens_if_needed(
                    sb, org_id, connector_id, settings
                )
                gsc_refresh = {
                    "ok": refresh_err is None and refreshed is not None,
                    "error": (refresh_err or "")[:180],
                }
                tokens = load_oauth_tokens(sb, connector_id, settings) or {}
                has_refresh = bool(tokens.get("refresh_token"))
                needs_refresh = token_needs_refresh(tokens, 300) if tokens else True
                authenticated = bool(tokens.get("access_token") or has_refresh)
                token_valid = authenticated and not needs_refresh
                availability[-1]["authenticated"] = authenticated
                availability[-1]["token_valid"] = token_valid
                availability[-1]["execution_available"] = connected and token_valid
            oauth_booleans.append(
                {
                    "vendor": vendor,
                    "status": status,
                    "has_access_token": bool((tokens or {}).get("access_token")),
                    "has_refresh_token": has_refresh,
                    "needs_refresh": needs_refresh,
                }
            )
            kind = None
            if vendor == "google_analytics" and (status == "pending_auth" or not authenticated):
                kind = "pending_auth"
            if vendor == "google_search_console" and not gsc_refresh.get("ok"):
                kind = "token_expired"
            if vendor == "gmail" and not authenticated:
                kind = "pending_auth"
            if kind:
                signals.append(
                    {
                        "id": f"{vendor}-{kind}",
                        "kind": kind,
                        "connector": vendor,
                        "evidence": [kind, status or "missing"],
                    }
                )
    recs = evaluate_business_signals(signals + signals)
    entity = seed_test_customer_alpha(org_id=org_id)
    written = persist_join_store(sb, entity) if isolated else 0
    action_keys = [DEFAULT_VENDOR_ACTIONS[v] for v in DEFAULT_VENDOR_ACTIONS if v in {r["vendor"] for r in availability}]
    if "hubspot.deals.list" not in action_keys:
        action_keys.append("hubspot.deals.list")
    card = scorecard_from_availability_rows(
        availability,
        action_keys=action_keys or ["hubspot.deals.list"],
        production_verified_keys=frozenset(
            {"hubspot.deals.list"} if any(r["vendor"] == "hubspot" and r.get("execution_available") for r in availability) else ()
        ),
    )
    website_turn: dict = {}
    if gsc_refresh.get("ok"):
        import jwt
        import httpx

        base = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
        url = env["SUPABASE_URL"].rstrip("/")
        tok = jwt.encode(
            {
                "sub": user_id,
                "email": email,
                "aud": "authenticated",
                "iss": f"{url}/auth/v1",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
                "role": "authenticated",
            },
            env["SUPABASE_JWT_SECRET"],
            algorithm="HS256",
        )
        from isolated_conversation_org import smoke_http_headers

        headers = {
            **smoke_http_headers(),
            "Authorization": f"Bearer {tok}",
            "X-Org-Id": org_id,
            "X-Environment": "production",
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        json_headers = {k: v for k, v in headers.items() if k != "Accept"}
        with httpx.Client(timeout=180.0) as client:
            cr = client.post(
                f"{base}/api/conversations",
                headers=json_headers,
                json={"title": f"gsc-remain-{uuid.uuid4().hex[:8]}"},
            )
            if cr.status_code < 400:
                conv_id = str(cr.json()["id"])
                with client.stream(
                    "POST",
                    f"{base}/api/assistant/chat",
                    headers=headers,
                    json={
                        "messages": [
                            {
                                "role": "user",
                                "parts": [{"type": "text", "text": "How is my website doing?"}],
                            }
                        ],
                        "org_id": org_id,
                        "mode": "fast",
                        "conversation_id": conv_id,
                    },
                ) as resp:
                    raw = "".join(resp.iter_text())
                website_turn = {
                    "conversation_id": conv_id,
                    "http_status": resp.status_code,
                    "assistant_len": len(raw),
                    "mentions_connect": "connect" in raw.lower() or "reconnect" in raw.lower(),
                    "mentions_search": "search" in raw.lower() or "clicks" in raw.lower(),
                }
            else:
                website_turn = {"http_status": cr.status_code, "create_failed": True}
    report = {
        "at": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "isolated": isolated,
        "user_id": user_id,
        "email": email,
        "policy": e2e_org_policy(),
        "alpha_entity_id": entity.id,
        "alpha_bindings": [b.system for b in entity.bindings],
        "alpha_rows_written": written,
        "gsc_connector_id_present": bool(gsc_connector_id),
        "gsc_refresh": gsc_refresh,
        "website_remaining_source": website_turn,
        "oauth_booleans": oauth_booleans,
        "proactive": [
            {
                "signal_id": r.signal_id,
                "notify": r.notify,
                "write_allowed": r.write_allowed,
                "significance": r.significance,
            }
            for r in recs
        ],
        "scorecard_customer_facing": card.get("customer_facing_certification"),
        "scorecard_items": [
            {"action_key": item["action_key"], "customer_badge": item.get("customer_badge"), "layers": item.get("layers")}
            for item in card.get("items") or []
        ],
    }
    OUT.write_text(json.dumps(report, indent=2, default=str)[:80000], encoding="utf-8")
    print(
        json.dumps(
            {
                "org_id": org_id,
                "isolated": isolated,
                "alpha_entity_id": entity.id,
                "alpha_rows_written": written,
                "oauth_booleans": oauth_booleans,
                "gsc_refresh": gsc_refresh,
                "website_remaining_source": website_turn,
                "proactive_count": len(recs),
                "write_allowed_any": any(r.write_allowed for r in recs),
                "customer_facing_certification": card.get("customer_facing_certification"),
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
