"""STA-270 paired evaluation smoke: CoordinationLayer flag off vs on (test org only).

Usage:
  python scripts/smoke-sta270-coordination-layer.py
  python scripts/smoke-sta270-coordination-layer.py --json docs/delivery/smoke-sta270-coordination-layer-latest.json
  python scripts/smoke-sta270-coordination-layer.py --expect-enabled   # after Railway flag on
  python scripts/smoke-sta270-coordination-layer.py --expect-disabled  # baseline 2A path
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
TEST_ORG = os.environ.get("COORDINATION_TEST_ORG", "00000000-0000-0000-0000-000000000001")
SMOKE_PREFIX = "STA-270 coordination smoke"
DECISION_DUE = "2026-08-01"
C6_DUE = "2026-07-05"


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


def _request(method: str, path: str, token: str, org_id: str, body: dict | None = None, *, timeout: int = 90) -> dict:
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
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required in backend/.env")
    now = int(time.time())
    return jwt.encode(
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


def _supabase_client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _test_org_actor(env: dict[str, str]) -> tuple[str, str, str]:
    client = _supabase_client(env)
    members = (
        client.table("organization_members")
        .select("user_id, role")
        .eq("org_id", TEST_ORG)
        .in_("role", ["admin", "owner"])
        .limit(1)
        .execute()
    )
    if not members.data:
        raise SystemExit(f"No admin member for test org {TEST_ORG}")
    user_id = str(members.data[0]["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return TEST_ORG, user_id, email


def _pick_agents(client, org_id: str) -> tuple[str, str]:
    rows = (
        client.table("agents")
        .select("id, name, status")
        .eq("org_id", org_id)
        .eq("status", "active")
        .limit(5)
        .execute()
    )
    data = rows.data or []
    if len(data) < 1:
        raise SystemExit(f"No active agents in org {org_id}")
    parent_id = str(data[0]["id"])
    sub_id = str(data[1]["id"]) if len(data) > 1 else parent_id
    return parent_id, sub_id


def run_smoke(*, json_path: Path | None = None, expect_enabled: bool | None = None) -> dict:
    env = _load_env()
    org_id, user_id, email = _test_org_actor(env)
    token = _mint_token(env, user_id, email)
    client = _supabase_client(env)
    steps: list[dict] = []

    def record(label: str, status: str, detail: str = "") -> None:
        steps.append({"label": label, "status": status, "detail": detail})
        print(f"[{status.upper()}] {label}" + (f": {detail}" if detail else ""))

    # 1) Health exposes coordination flag (no auth)
    try:
        with urllib.request.urlopen(f"{API_BASE}/health", timeout=30) as resp:
            health = json.loads(resp.read().decode("utf-8") or "{}")
        coord = health.get("coordinationLayer") or {}
        enabled = bool(coord.get("enabled"))
        record("health_coordination_flag", "pass", f"enabled={enabled} allowedOrgCount={coord.get('allowedOrgCount')}")
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        enabled = False
        record("health_coordination_flag", "fail", str(exc))

    if expect_enabled is not None:
        if enabled == expect_enabled:
            record("expect_flag_state", "pass", f"enabled={enabled}")
        else:
            record("expect_flag_state", "fail", f"expected enabled={expect_enabled} got {enabled}")

    # 2) Swarm start on test org — coordinationLayer marker when flag on
    parent_id, sub_id = _pick_agents(client, org_id)
    objective = f"{SMOKE_PREFIX} {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    try:
        swarm = _request(
            "POST",
            "/api/agent-swarm/start",
            token,
            org_id,
            {
                "parentAgentId": parent_id,
                "objective": objective,
                "subtasks": [{"agentId": sub_id, "task": "Summarize coordination smoke objective.", "scopedTools": []}],
            },
        )
        swarm_id = str(swarm.get("id") or "")
        coord_on = bool(swarm.get("coordinationLayer"))
        record("swarm_start", "pass", f"swarmId={swarm_id} coordinationLayer={coord_on}")
        if enabled and org_id == TEST_ORG:
            if coord_on:
                record("swarm_coordination_marker", "pass", "coordinationLayer=true")
            else:
                record("swarm_coordination_marker", "fail", "flag enabled but response missing coordinationLayer")
        elif not enabled:
            if not coord_on:
                record("swarm_baseline_path", "pass", "2A path (no coordinationLayer marker)")
            else:
                record("swarm_baseline_path", "warn", "unexpected coordinationLayer on disabled flag")

        job_id = None
        subtasks = swarm.get("subtasks") or []
        if subtasks and isinstance(subtasks[0], dict):
            job_id = subtasks[0].get("agentJobId")
        if enabled and job_id:
            job_row = (
                client.table("agent_jobs")
                .select("payload")
                .eq("id", job_id)
                .limit(1)
                .execute()
            )
            payload = (job_row.data or [{}])[0].get("payload") or {}
            if isinstance(payload, dict) and payload.get("coordinationContext"):
                record("swarm_job_coordination_context", "pass", "coordinationContext in job payload")
            else:
                record("swarm_job_coordination_context", "fail", "missing coordinationContext in job payload")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        record("swarm_start", "fail", f"HTTP {exc.code}: {body[:240]}")

    passed = sum(1 for s in steps if s["status"] == "pass")
    failed = sum(1 for s in steps if s["status"] == "fail")
    report = {
        "target": API_BASE,
        "orgId": org_id,
        "testOrgOnly": True,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "coordinationLayerEnabled": enabled,
        "evaluationWindowEnd": DECISION_DUE,
        "sta271C6Scheduled": C6_DUE,
        "summary": {"pass": passed, "fail": failed, "total": len(steps)},
        "steps": steps,
    }
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {json_path}")
    if failed:
        sys.exit(1)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--expect-enabled", action="store_true")
    parser.add_argument("--expect-disabled", action="store_true")
    args = parser.parse_args()
    expect: bool | None = None
    if args.expect_enabled:
        expect = True
    elif args.expect_disabled:
        expect = False
    run_smoke(json_path=args.json, expect_enabled=expect)


if __name__ == "__main__":
    main()
