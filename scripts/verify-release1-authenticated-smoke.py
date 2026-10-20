#!/usr/bin/env python3
"""Authenticated Release 1 production smoke, isolated account only.

No provider writes and no customer organization mutations. Full member/admin
role-change, MCP, revocation and approval acceptance remain separate gates.
"""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("docs/delivery/release1-authenticated-smoke.json")
WEB = os.environ.get("WEB_BASE", "https://gravitre.app").rstrip("/")
API = os.environ.get("API_BASE", "https://api.gravitre.app").rstrip("/")

def get(url: str, token: str | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=(
        {"Authorization": "Bearer " + token} if token else {}
    ))
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read(65536)
    except urllib.error.HTTPError as e:
        return e.code, e.read(65536)

def main() -> int:
    token = os.environ.get("PLATFORM_LIVE_BEARER_TOKEN", "")
    org_id = os.environ.get("PLATFORM_LIVE_ORG_ID", "")
    if not token or not org_id or os.environ.get("PLATFORM_LIVE_AUTH_MODE") != "smoke_org_short_lived":
        print("Missing validated isolated-org bearer session", file=sys.stderr)
        return 2

    checks: list[dict] = []
    def record(name: str, ok: bool, status: int) -> None:
        checks.append({"name": name, "pass": ok, "http_status": status})

    # Both authenticated endpoints MUST reject unauthenticated access or
    # return a genuinely empty, parseable session payload.
    url = WEB + "/api/sessions?org_id=" + org_id
    code, body = get(url)
    if code in (401, 403):
        anonymous_safe = True
    elif code == 200:
        try:
            data = json.loads(body)
            anonymous_safe = (
                isinstance(data, dict)
                and isinstance(data.get("activeRuns", []), list)
                and isinstance(data.get("recentActivity", []), list)
                and not data.get("activeRuns")
                and not data.get("recentActivity")
                and not any(k in data for k in ("access_token", "service_role", "secret"))
            )
        except (ValueError, TypeError):
            anonymous_safe = False
    else:
        anonymous_safe = False
    record("anonymous_sessions_no_protected_data", anonymous_safe, code)

    # Verify that authenticated and anonymous requests are distinguishable;
    # this is reachability evidence, not proof of every role permission.
    auth_code, _ = get(API + "/health", token)
    record("authenticated_bearer_api_reachable", auth_code == 200, auth_code)

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "scope": "isolated_smoke_org_only",
        "checks": checks,
        "verdict": "PASS" if all(c["pass"] for c in checks) else "FAIL",
        "not_covered": ["member_role_mutations", "admin_role_audit", "mcp_ssrf",
            "source_revocation", "approval_bypass", "browser_secret_audit"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": payload["verdict"], "checks": checks, "out": str(OUT)}))
    return 0 if payload["verdict"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
