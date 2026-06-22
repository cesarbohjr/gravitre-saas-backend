"""Production smoke: swarm subtasks + council aggregate must reach completed.

Usage:
  npm run smoke:swarm-council-lifecycle
  npm run smoke:swarm-council-lifecycle:report
"""
from __future__ import annotations

import argparse
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
ENV_BACKEND = REPO / "backend" / ".env"
ENV_OPERATOR = REPO / "backend" / ".env.operator.local"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"
TEST_ORG = os.environ.get("SMOKE_ORG_ID", "00000000-0000-0000-0000-000000000001")
OBJECTIVE = "Swarm council lifecycle smoke: assess vendor integration risk"
SUBTASK_TIMEOUT_S = 180
AGGREGATE_POLL_S = 240
TERMINAL_SUBTASK = {"completed", "failed", "cancelled"}
SWARM_TERMINAL = {"completed", "failed", "cancelled"}


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_OPERATOR):
        if not path.is_file():
            continue
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                values = dotenv_values(path, encoding=encoding)
                merged.update({k: v for k, v in values.items() if v})
                break
            except UnicodeDecodeError:
                continue
    return merged


def _request(method: str, path: str, token: str, org_id: str, body: dict | None = None, *, timeout: int = 120) -> dict:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw) if raw.strip() else {}


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "role": "authenticated",
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
        },
        secret,
        algorithm="HS256",
    )


def _supabase_client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _pick_agents(client, org_id: str, *, count: int = 2) -> tuple[str, list[str]]:
    rows = (
        client.table("agents")
        .select("id,name,role,status")
        .eq("org_id", org_id)
        .eq("status", "active")
        .limit(10)
        .execute()
    ).data or []
    if len(rows) < count + 1:
        raise RuntimeError(f"Need at least {count + 1} active agents in org {org_id}")
    parent_id = str(rows[0]["id"])
    sub_ids = [str(r["id"]) for r in rows[1 : count + 1]]
    return parent_id, sub_ids


def _org_actor(env: dict[str, str], org_id: str) -> tuple[str, str]:
    client = _supabase_client(env)
    members = (
        client.table("organization_members")
        .select("user_id, role")
        .eq("org_id", org_id)
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if not members.data:
        members = (
            client.table("organization_members")
            .select("user_id, role")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
    if not members.data:
        raise SystemExit(f"No organization_members row found for org {org_id}")
    user_id = str(members.data[0]["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return user_id, email


def run_smoke() -> dict:
    env = _load_env()
    org_id = TEST_ORG
    user_id, email = _org_actor(env, org_id)
    token = _mint_token(env, user_id, email)
    client = _supabase_client(env)
    parent_id, sub_ids = _pick_agents(client, org_id, count=2)

    t0 = time.perf_counter()
    swarm = _request(
        "POST",
        "/api/agent-swarm/start",
        token,
        org_id,
        {
            "parentAgentId": parent_id,
            "objective": OBJECTIVE,
            "subtasks": [
                {"agentId": sub_ids[0], "task": "Review security and compliance risks.", "scopedTools": []},
                {"agentId": sub_ids[1], "task": "Review integration effort and timeline.", "scopedTools": []},
            ],
        },
    )
    swarm_id = str(swarm.get("id") or "")
    if not swarm_id:
        raise RuntimeError("swarm start returned no id")

    deadline = time.time() + SUBTASK_TIMEOUT_S
    last = swarm
    while time.time() < deadline:
        last = _request("GET", f"/api/agent-swarm/{swarm_id}", token, org_id)
        subtasks = last.get("subtasks") or []
        if subtasks and all(str(s.get("status") or "") in TERMINAL_SUBTASK for s in subtasks if isinstance(s, dict)):
            break
        time.sleep(5)
    else:
        raise RuntimeError(f"Subtasks did not finish within {SUBTASK_TIMEOUT_S}s")

    status = str(last.get("status") or "")
    if status in {"running", "pending"}:
        try:
            last = _request("POST", f"/api/agent-swarm/{swarm_id}/aggregate", token, org_id, {})
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                raise

    poll_deadline = time.time() + AGGREGATE_POLL_S
    while time.time() < poll_deadline:
        last = _request("GET", f"/api/agent-swarm/{swarm_id}", token, org_id)
        status = str(last.get("status") or "")
        if status in SWARM_TERMINAL:
            break
        time.sleep(3)

    total_ms = int((time.perf_counter() - t0) * 1000)
    passed = status == "completed" and bool(last.get("finalRecommendation") or last.get("final_recommendation"))
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "target": API_BASE,
        "orgId": org_id,
        "swarmId": swarm_id,
        "status": status,
        "finalRecommendation": last.get("finalRecommendation") or last.get("final_recommendation"),
        "finalConfidence": last.get("finalConfidence") or last.get("final_confidence"),
        "councilSessionId": last.get("councilSessionId") or last.get("council_session_id"),
        "errorMessage": last.get("errorMessage") or last.get("error_message"),
        "timingMs": {"total": total_ms},
        "pass": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    result = run_smoke()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Wrote {args.json}")
    print(
        f"Swarm council lifecycle: status={result['status']} "
        f"recommendation={result['finalRecommendation']} pass={result['pass']}"
    )
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
