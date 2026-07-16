#!/usr/bin/env python3
"""STA-321 live: pack install → default agent resolve → assignment without manual pick.

Mirrors apps/web/lib/resolve-default-agent.ts against prod installs/agents, then
creates an assignment with the resolved agent_id (the UI no longer requires a
choose-agent step when this resolves).

Usage:
  python scripts/smoke-sta321-auto-agent-live.py
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
BACKEND = REPO / "backend"

API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
ENV_NAME = "production"
OUT = REPO / "docs" / "delivery" / "sta321-auto-agent-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in os.environ.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)
    return merged


def mint(env: dict[str, str], user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def request(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict | list]:
    url = f"{API_BASE}{path}"
    url += ("&" if "?" in path else "?") + f"environment={ENV_NAME}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", ORG)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def collect_installed_agent_ids(installs: list[dict]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for install in installs:
        status = str(install.get("status") or "active").lower()
        if status not in {"active", "installed"}:
            continue
        meta = install.get("metadata") or {}
        candidates = list(meta.get("agentIds") or [])
        if meta.get("agentId"):
            candidates.append(meta["agentId"])
        if install.get("installedEntityType") == "agent" and install.get("installedEntityId"):
            candidates.append(install["installedEntityId"])
        for agent_id in candidates:
            if isinstance(agent_id, str) and agent_id and agent_id not in seen:
                seen.add(agent_id)
                ids.append(agent_id)
    return ids


def is_pack_backed(agent: dict) -> bool:
    config = agent.get("config") or {}
    return bool(
        config.get("marketplaceAssetId")
        or config.get("pack_id")
        or config.get("packId")
        or config.get("marketplace_asset_id")
    )


def resolve_default_agent_id(agents: list[dict], installed: list[str]) -> str | None:
    active = [a for a in agents if not a.get("status") or a.get("status") == "active"]
    pool = active or agents
    if not pool:
        return None
    by_id = {a["id"]: a for a in pool if a.get("id")}
    for agent_id in installed:
        if agent_id in by_id:
            return agent_id
    for agent in pool:
        if is_pack_backed(agent):
            return agent["id"]
    return pool[0].get("id")


def main() -> int:
    env = load_env()
    email = env.get("SMOKE_USER_EMAIL") or "cesar@gravitre.app"
    token = mint(env, ACTOR, email)

    status_i, installs_body = request("GET", "/api/marketplace/installs?status=active&limit=100", token)
    status_a, agents_body = request("GET", "/api/agents", token)

    installs = []
    if isinstance(installs_body, dict):
        installs = installs_body.get("installs") or []
    agents = []
    if isinstance(agents_body, dict):
        agents = agents_body.get("agents") or []

    installed_ids = collect_installed_agent_ids(installs if isinstance(installs, list) else [])
    resolved = resolve_default_agent_id(agents if isinstance(agents, list) else [], installed_ids)
    resolved_agent = next((a for a in agents if a.get("id") == resolved), None) if resolved else None

    assignment: dict = {}
    assign_status = 0
    if resolved:
        # Next.js /api/assignments proxies to FastAPI /api/agent-jobs
        assign_status, assignment = request(
            "POST",
            "/api/agent-jobs",
            token,
            {
                "task": f"STA-321 auto-agent smoke — summarize open approvals ({utcnow()})",
                "agent_id": resolved,
                "context": {"priority": "normal", "source": "sta321-smoke"},
            },
        )
    if not isinstance(assignment, dict):
        assignment = {}

    artifact = {
        "ticket": "STA-321",
        "at": utcnow(),
        "org_id": ORG,
        "api_base": API_BASE,
        "installs_http": status_i,
        "agents_http": status_a,
        "active_install_count": len(installs) if isinstance(installs, list) else 0,
        "agent_count": len(agents) if isinstance(agents, list) else 0,
        "installed_agent_ids": installed_ids[:20],
        "resolved_agent_id": resolved,
        "resolved_agent_name": (resolved_agent or {}).get("name"),
        "resolved_pack_backed": is_pack_backed(resolved_agent) if resolved_agent else False,
        "assignment_http": assign_status,
        "assignment_id": assignment.get("id") or assignment.get("jobId") or assignment.get("job_id"),
        "assignment_status": assignment.get("status"),
        "pass": bool(
            status_i < 400
            and status_a < 400
            and resolved
            and assign_status < 400
            and (assignment.get("id") or assignment.get("jobId") or assignment.get("job_id"))
        ),
        "notes": (
            "UI skips Assignments choose-agent when resolveDefaultAgentId succeeds; "
            "this smoke proves the same resolve + assignment create path on prod."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0 if artifact["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
