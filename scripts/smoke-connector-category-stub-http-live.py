#!/usr/bin/env python3
"""HTTP live smoke: install connector-category stubs via marketplace API on PROD.

Uses real JWT + X-Org-Id against Railway backend (not service-role-only install).
Soft-deletes leftover probe stubs via service role only for clean install, then
POSTs /api/marketplace/connector-category-templates/{id}/install.

Writes docs/delivery/phase1-needs-connection-stub-http-live.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
PROBE_TYPES = [
    "fred",
    "zoominfo",
    "linkedin_sales_navigator",
    "sec_edgar",
    "world_bank",
    "oecd",
    "opencorporates",
]
TEMPLATES = [
    "executive-intelligence-sources",
    "byo-premium-prospecting",
]
REQUIRED_TEMPLATE_IDS = frozenset(TEMPLATES)
OUT = REPO / "docs" / "delivery" / "phase1-needs-connection-stub-http-live.json"
FORBIDDEN_STATUSES = frozenset({"active", "connected", "healthy"})
EXPECTED_AUTH = {
    "fred": "gravitree_managed",
    "sec_edgar": "gravitree_managed",
    "world_bank": "gravitree_managed",
    "oecd": "gravitree_managed",
    "opencorporates": "gravitree_managed",
    "zoominfo": "byo_required",
    "linkedin_sales_navigator": "byo_required",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if p.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(p).items() if v})
            except UnicodeDecodeError:
                pass
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _mint_jwt(client) -> str:
    email = client.auth.admin.get_user_by_id(ACTOR).user.email
    url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_JWT_SECRET"]
    now = int(time.time())
    return jwt.encode(
        {
            "sub": ACTOR,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _soft_delete_probe_stubs(client, org_id: str, types: list[str]) -> list[dict]:
    """Service-role cleanup of leftover stubs so HTTP install can create fresh rows.

    Documented: HTTP install is idempotent and skips existing types; soft-delete
    via service role is only for a clean create-path proof, not for install itself.
    """
    now = utcnow()
    cleaned: list[dict] = []
    for ctype in types:
        rows = (
            client.table("connectors")
            .select("id, type, status, deleted_at")
            .eq("org_id", org_id)
            .eq("type", ctype)
            .is_("deleted_at", "null")
            .execute()
            .data
            or []
        )
        for row in rows:
            client.table("connectors").update({"deleted_at": now}).eq("id", row["id"]).eq(
                "org_id", org_id
            ).execute()
            cleaned.append(
                {
                    "id": row["id"],
                    "type": row.get("type"),
                    "priorStatus": row.get("status"),
                    "deleted_at": now,
                }
            )
    return cleaned


def _query_created(client, org_id: str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    rows = (
        client.table("connectors")
        .select("id, type, status, config, deleted_at")
        .eq("org_id", org_id)
        .in_("id", ids)
        .execute()
        .data
        or []
    )
    return [dict(r) for r in rows]


def _fetch_health(http: httpx.Client) -> dict:
    r = http.get(f"{BASE}/health")
    try:
        return r.json() if r.content else {}
    except Exception:  # noqa: BLE001
        return {"_raw": r.text, "_status": r.status_code}


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)

    ran_at = utcnow()
    out: dict = {
        "pass": False,
        "prod_git_sha": None,
        "ran_at": ran_at,
        "base": BASE,
        "org_id": ORG,
        "actor_id": ACTOR,
        "note": (
            "HTTP install via marketplace API with admin JWT; "
            "service-role soft-delete used only for pre-clean leftover stubs "
            "and post-verify cleanup — not for install itself."
        ),
        "get_status": None,
        "get_template_ids": [],
        "pre_cleanup": [],
        "posts": {},
        "created": [],
        "skipped": [],
        "statuses": {},
        "auth_modes": {},
        "staged_counts": {},
        "zero_live_connections": False,
        "db_rows": [],
        "cleanup": {"ok": False, "soft_deleted": [], "error": None},
        "assertions": [],
        "errors": [],
    }

    try:
        token = _mint_jwt(client)
    except Exception as exc:  # noqa: BLE001
        out["errors"].append(f"jwt_mint_failed: {exc}")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(out, indent=2))
        return 1

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Content-Type": "application/json",
    }

    with httpx.Client(verify=False, timeout=120) as http:
        health = _fetch_health(http)
        out["prod_git_sha"] = health.get("git_sha")

        # GET templates
        get_r = http.get(f"{BASE}/api/marketplace/connector-category-templates", headers=headers)
        out["get_status"] = get_r.status_code
        get_body: dict = {}
        try:
            get_body = get_r.json() if get_r.content else {}
        except Exception:  # noqa: BLE001
            get_body = {"_raw": get_r.text[:500]}

        if get_r.status_code == 404:
            out["errors"].append("GET connector-category-templates returned 404 — deploy not live")
            out["assertions"].append(
                {"name": "get_templates_route", "ok": False, "detail": "HTTP 404"}
            )
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(out, indent=2))
            return 1

        if get_r.status_code in (401, 403):
            out["errors"].append(
                f"GET auth blocked: {get_r.status_code} body={json.dumps(get_body)[:300]}"
            )
            out["assertions"].append(
                {
                    "name": "get_templates_auth",
                    "ok": False,
                    "detail": f"HTTP {get_r.status_code}",
                }
            )
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(out, indent=2))
            return 1

        if get_r.status_code != 200:
            out["errors"].append(f"GET unexpected status {get_r.status_code}")
            out["assertions"].append(
                {
                    "name": "get_templates_200",
                    "ok": False,
                    "detail": f"HTTP {get_r.status_code}",
                }
            )
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(out, indent=2))
            return 1

        items = get_body.get("items") or []
        ids = {str(i.get("id")) for i in items if isinstance(i, dict)}
        out["get_template_ids"] = sorted(ids)
        missing = sorted(REQUIRED_TEMPLATE_IDS - ids)
        get_ok = not missing
        out["assertions"].append(
            {
                "name": "get_templates_includes_required",
                "ok": get_ok,
                "missing": missing,
                "count": get_body.get("count"),
            }
        )
        if not get_ok:
            out["errors"].append(f"missing_templates:{missing}")

        # Pre-clean leftover stubs (service role) for clean HTTP create path
        try:
            out["pre_cleanup"] = _soft_delete_probe_stubs(client, ORG, PROBE_TYPES)
            out["assertions"].append(
                {
                    "name": "pre_cleanup_service_role",
                    "ok": True,
                    "soft_deleted_count": len(out["pre_cleanup"]),
                    "note": "service-role soft-delete of leftover stubs only — install is HTTP",
                }
            )
        except Exception as exc:  # noqa: BLE001
            out["errors"].append(f"pre_cleanup_failed: {exc}")
            out["assertions"].append(
                {"name": "pre_cleanup_service_role", "ok": False, "detail": str(exc)}
            )
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(out, indent=2))
            return 1

        created_ids: list[str] = []
        post_ok = True
        for template_id in TEMPLATES:
            post_r = http.post(
                f"{BASE}/api/marketplace/connector-category-templates/{template_id}/install",
                headers=headers,
            )
            post_body: dict = {}
            try:
                post_body = post_r.json() if post_r.content else {}
            except Exception:  # noqa: BLE001
                post_body = {"_raw": post_r.text[:500]}

            entry = {
                "status_code": post_r.status_code,
                "stagedCount": post_body.get("stagedCount"),
                "created": post_body.get("created") or [],
                "skipped": post_body.get("skipped") or [],
                "installed": post_body.get("installed"),
                "body_keys": sorted(post_body.keys()) if isinstance(post_body, dict) else [],
            }
            out["posts"][template_id] = entry
            out["staged_counts"][template_id] = post_body.get("stagedCount")

            if post_r.status_code == 404:
                post_ok = False
                out["errors"].append(
                    f"POST {template_id} returned 404 — deploy not live / unknown template"
                )
                continue
            if post_r.status_code in (401, 403):
                post_ok = False
                out["errors"].append(
                    f"POST {template_id} auth blocked: {post_r.status_code} "
                    f"body={json.dumps(post_body)[:300]}"
                )
                continue
            if post_r.status_code != 200:
                post_ok = False
                out["errors"].append(f"POST {template_id} unexpected status {post_r.status_code}")
                continue

            for row in post_body.get("created") or []:
                cid = row.get("id")
                if cid:
                    created_ids.append(str(cid))
                out["created"].append({**row, "templateId": template_id})
            for skip in post_body.get("skipped") or []:
                out["skipped"].append({**skip, "templateId": template_id})

            staged = post_body.get("stagedCount")
            created_list = post_body.get("created") or []
            if staged is None and not created_list:
                post_ok = False
                out["errors"].append(f"POST {template_id}: no stagedCount and empty created")
            elif staged is not None and staged == 0 and not created_list:
                # All skipped — not a create-path proof
                post_ok = False
                out["errors"].append(f"POST {template_id}: stagedCount=0 (all skipped?)")

        out["assertions"].append(
            {
                "name": "post_install_200",
                "ok": post_ok,
                "templates": TEMPLATES,
            }
        )

        # Assert created statuses from HTTP response
        created_ok = True
        for row in out["created"]:
            status = str(row.get("status") or "")
            ctype = str(row.get("connectorType") or "")
            cid = str(row.get("id") or "")
            out["statuses"][cid] = status
            out["auth_modes"][cid] = row.get("authMode")
            if status != "needs_connection":
                created_ok = False
                out["errors"].append(f"created_status_not_needs_connection:{ctype}:{status}")
            if status in FORBIDDEN_STATUSES:
                created_ok = False
                out["errors"].append(f"forbidden_live_status:{ctype}:{status}")
            expected = EXPECTED_AUTH.get(ctype)
            if expected and row.get("authMode") != expected:
                created_ok = False
                out["errors"].append(
                    f"auth_mode_mismatch:{ctype}:got={row.get('authMode')}:want={expected}"
                )

        zero_live = bool(out["created"]) and all(
            str(s) not in FORBIDDEN_STATUSES for s in out["statuses"].values()
        )
        out["zero_live_connections"] = zero_live and created_ok and bool(out["created"])

        out["assertions"].append(
            {
                "name": "created_status_needs_connection",
                "ok": created_ok and bool(out["created"]),
                "createdCount": len(out["created"]),
            }
        )
        out["assertions"].append(
            {
                "name": "no_live_statuses_on_created",
                "ok": zero_live,
            }
        )

        # Optional DB verify
        db_ok = True
        try:
            db_rows = _query_created(client, ORG, created_ids)
            out["db_rows"] = [
                {
                    "id": r.get("id"),
                    "type": r.get("type"),
                    "status": r.get("status"),
                    "auth_mode": (r.get("config") or {}).get("auth_mode"),
                    "deleted_at": r.get("deleted_at"),
                }
                for r in db_rows
            ]
            by_id = {str(r["id"]): r for r in db_rows}
            for cid in created_ids:
                row = by_id.get(cid)
                if not row:
                    db_ok = False
                    out["errors"].append(f"db_missing:{cid}")
                    continue
                if str(row.get("status")) != "needs_connection":
                    db_ok = False
                    out["errors"].append(f"db_status:{cid}:{row.get('status')}")
                if str(row.get("status")) in FORBIDDEN_STATUSES:
                    db_ok = False
                    out["errors"].append(f"db_forbidden_status:{cid}:{row.get('status')}")
                ctype = str(row.get("type") or "")
                auth = (row.get("config") or {}).get("auth_mode")
                expected = EXPECTED_AUTH.get(ctype)
                if expected and auth != expected:
                    db_ok = False
                    out["errors"].append(f"db_auth_mode:{cid}:{ctype}:{auth}")
                out["statuses"][cid] = row.get("status")
                out["auth_modes"][cid] = auth
        except Exception as exc:  # noqa: BLE001
            db_ok = False
            out["errors"].append(f"db_query_failed: {exc}")

        out["assertions"].append({"name": "db_status_and_auth_mode", "ok": db_ok})

        # Soft-delete created stubs after verify
        cleanup_ok = False
        try:
            now = utcnow()
            soft_deleted: list[str] = []
            for cid in created_ids:
                client.table("connectors").update({"deleted_at": now}).eq("id", cid).eq(
                    "org_id", ORG
                ).execute()
                soft_deleted.append(cid)
            confirm = _query_created(client, ORG, created_ids)
            still_live = [r["id"] for r in confirm if not r.get("deleted_at")]
            cleanup_ok = len(still_live) == 0
            out["cleanup"] = {
                "ok": cleanup_ok,
                "soft_deleted": soft_deleted,
                "error": None if cleanup_ok else f"still_not_deleted:{still_live}",
                "deleted_at": now,
            }
        except Exception as exc:  # noqa: BLE001
            out["cleanup"] = {"ok": False, "soft_deleted": [], "error": str(exc)}

        out["assertions"].append({"name": "cleanup_soft_delete", "ok": cleanup_ok})

    all_ok = (
        get_ok
        and post_ok
        and created_ok
        and db_ok
        and cleanup_ok
        and bool(out["created"])
        and out["zero_live_connections"]
        and not out["errors"]
        and all(a.get("ok") for a in out["assertions"])
    )
    out["pass"] = all_ok
    out["finished_at"] = utcnow()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
