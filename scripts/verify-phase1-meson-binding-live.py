"""Phase 1 live: Meson deploy must leave a builder graph with real edges.

Usage:
  python scripts/verify-phase1-meson-binding-live.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "delivery" / "phase1-meson-binding-live.json"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")


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
    # Meson requires control+; prefer explicit smoke org, then any active control/command sub.
    preferred = (
        os.environ.get("SMOKE_ORG_ID")
        or env.get("SMOKE_ORG_ID")
        or "f07e57c0-1501-4000-8000-c04e57a00001"
    ).strip()
    org_id = ""
    user_id = ""
    for candidate in (preferred,):
        members = (
            sb.table("organization_members")
            .select("org_id, user_id, role")
            .eq("org_id", candidate)
            .eq("role", "admin")
            .limit(1)
            .execute()
        )
        if members.data:
            org_id = str(members.data[0]["org_id"])
            user_id = str(members.data[0]["user_id"])
            break
    if not org_id:
        subs = (
            sb.table("subscriptions")
            .select("org_id, tier, status")
            .eq("status", "active")
            .in_("tier", ["control", "command"])
            .limit(20)
            .execute()
        )
        for sub in subs.data or []:
            members = (
                sb.table("organization_members")
                .select("org_id, user_id, role")
                .eq("org_id", str(sub["org_id"]))
                .eq("role", "admin")
                .limit(1)
                .execute()
            )
            if members.data:
                org_id = str(members.data[0]["org_id"])
                user_id = str(members.data[0]["user_id"])
                break
    if not org_id:
        print("FAIL no control/command admin org")
        return 1
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
    intent = f"Phase1 Meson binding verify {uuid.uuid4().hex[:8]}: qualify leads and notify Slack"
    status, deployed = _request(
        "POST",
        "/api/meson/deploy",
        token,
        org_id,
        {
            "intent": intent,
            "department": "sales",
            "systems": ["crm", "slack"],
            "output_types": ["workflows", "tasks"],
            "create_workflow": True,
        },
    )
    report: dict = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "api_git_sha": health.get("git_sha"),
        "deploy_http": status,
        "deploy": deployed if isinstance(deployed, dict) else {"raw": deployed},
    }
    if status not in {200, 201}:
        report["verdict"] = "FAIL_DEPLOY"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2)[:2000])
        return 1

    workflow_id = str(
        (deployed or {}).get("workflowId")
        or (deployed or {}).get("workflow_id")
        or ""
    )
    report["workflow_id"] = workflow_id
    if not workflow_id:
        report["verdict"] = "FAIL_NO_WORKFLOW"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    g_status, graph = _request("GET", f"/api/workflows/{workflow_id}/builder", token, org_id)
    nodes = (graph or {}).get("nodes") or []
    edges = (graph or {}).get("edges") or []
    report["builder_http"] = g_status
    report["node_count"] = len(nodes)
    report["edge_count"] = len(edges)
    report["verdict"] = (
        "PASS"
        if g_status == 200 and len(nodes) >= 2 and len(edges) >= 1
        else "FAIL_EMPTY_GRAPH"
    )
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "checked_at", "api_git_sha", "deploy_http", "workflow_id",
        "node_count", "edge_count", "verdict",
    )}, indent=2))
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
