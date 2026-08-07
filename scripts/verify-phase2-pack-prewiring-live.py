"""Phase 2 live: install a published workflow and confirm builder edges on tip.

Usage:
  python scripts/verify-phase2-pack-prewiring-live.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "delivery" / "phase2-pack-prewiring-live.json"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ORG = os.environ.get("SMOKE_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")
# Default: no required connectors so smoke org can install without OAuth.
SLUG = os.environ.get("PHASE2_PACK_SLUG", "competitive-intelligence-monitoring")


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if not path.is_file():
            continue
        try:
            parsed = {k: v for k, v in dotenv_values(path).items() if v}
        except UnicodeDecodeError:
            parsed = {}
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, _, val = raw.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and val:
                    parsed[key] = val
        merged.update(parsed)
    return merged


def _request(method: str, path: str, token: str, org_id: str, body: dict | None = None):
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {"detail": raw}
        return exc.code, detail


def main() -> int:
    env = _load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    members = (
        sb.table("organization_members")
        .select("org_id, user_id, role")
        .eq("org_id", ORG)
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if not members.data:
        print("FAIL no admin in smoke org", ORG)
        return 1
    org_id = str(members.data[0]["org_id"])
    user_id = str(members.data[0]["user_id"])
    users = sb.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    secret = env["SUPABASE_JWT_SECRET"]
    supabase_url = env["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )

    health = json.load(urllib.request.urlopen(f"{API_BASE}/health", timeout=30))
    rows = (
        sb.table("marketplace_assets")
        .select("id, slug, asset_type")
        .eq("slug", SLUG)
        .limit(1)
        .execute()
    )
    asset = (rows.data or [None])[0]
    report: dict = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "api_git_sha": health.get("git_sha"),
        "org_id": org_id,
        "slug": SLUG,
    }
    if not asset:
        report["verdict"] = "FAIL_NO_ASSET"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2)[:2000])
        return 1

    asset_id = str(asset["id"])
    report["asset_id"] = asset_id
    inst_st, installed = _request(
        "POST",
        f"/api/marketplace/assets/{asset_id}/install",
        token,
        org_id,
        {"force": True},
    )
    report["install_http"] = inst_st
    report["install"] = installed if isinstance(installed, dict) else {"raw": installed}
    if inst_st not in {200, 201}:
        report["verdict"] = "FAIL_INSTALL"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2)[:2500])
        return 1

    workflow_id = str(
        (installed or {}).get("workflowId")
        or (installed or {}).get("workflow_id")
        or ""
    )
    if not workflow_id and isinstance(installed, dict):
        entities = installed.get("entities") if isinstance(installed.get("entities"), dict) else {}
        workflow_id = str(entities.get("workflowId") or entities.get("workflow_id") or "")
        if not workflow_id:
            for key in ("workflow", "installedWorkflow", "result"):
                blob = installed.get(key)
                if isinstance(blob, dict):
                    workflow_id = str(blob.get("id") or blob.get("workflowId") or "")
                    if workflow_id:
                        break
    report["workflow_id"] = workflow_id
    if not workflow_id:
        report["verdict"] = "FAIL_NO_WORKFLOW"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2)[:2500])
        return 1

    g_st, graph = _request("GET", f"/api/workflows/{workflow_id}/builder", token, org_id)
    nodes = (graph or {}).get("nodes") or []
    edges = (graph or {}).get("edges") or []
    report["builder_http"] = g_st
    report["node_count"] = len(nodes)
    report["edge_count"] = len(edges)
    report["verdict"] = (
        "PASS"
        if g_st == 200 and len(nodes) >= 2 and len(edges) >= 1
        else "FAIL_EMPTY_GRAPH"
    )
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "checked_at",
                    "api_git_sha",
                    "slug",
                    "workflow_id",
                    "node_count",
                    "edge_count",
                    "verdict",
                    "install_http",
                )
            },
            indent=2,
        )
    )
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
