#!/usr/bin/env python3
"""Non-destructive live proof for Plays readiness and observe routes.

This script performs GET requests only. It never binds workflows, executes
workflows, calls connector WRITE actions, or records business outcomes.

Required environment:
  PLAYS_LIVE_BEARER_TOKEN  authenticated user JWT
  PLAYS_LIVE_ORG_ID        tenant/org id

Optional:
  BACKEND_URL              defaults to production Railway backend
  PLAYS_LIVE_ENVIRONMENT   defaults to production

Output:
  docs/delivery/plays-readonly-live.json
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "delivery" / "plays-readonly-live.json"
BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")


def _required(name: str) -> str:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


def _get(client: httpx.Client, path: str) -> dict:
    response = client.get(path)
    payload = None
    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text[:500]}
    return {
        "path": path,
        "status_code": response.status_code,
        "payload": payload,
    }


def main() -> int:
    token = _required("PLAYS_LIVE_BEARER_TOKEN")
    org_id = _required("PLAYS_LIVE_ORG_ID")
    environment = os.environ.get("PLAYS_LIVE_ENVIRONMENT", "production")

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "X-Environment": environment,
    }
    paths = [
        "/health",
        "/api/plays",
        "/api/plays/revenue-recovery/readiness",
        "/api/plays/revenue-recovery/observe",
        "/api/plays/customer-rescue/readiness",
        "/api/plays/customer-rescue/observe",
        "/api/plays/marketing-performance/readiness",
        "/api/plays/marketing-performance/observe",
    ]

    with httpx.Client(base_url=BASE, headers=headers, timeout=90.0) as client:
        probes = [_get(client, path) for path in paths]

    failures: list[str] = []
    for probe in probes:
        if probe["status_code"] != 200:
            failures.append(f'{probe["path"]}:HTTP_{probe["status_code"]}')

    for probe in probes:
        path = probe["path"]
        payload = probe["payload"] if isinstance(probe["payload"], dict) else {}
        if path.endswith("/observe") and probe["status_code"] == 200:
            if payload.get("actionTaken") is not False:
                failures.append(f"{path}:actionTaken_not_false")
        if path == "/api/plays" and probe["status_code"] == 200:
            if payload.get("executionAuthority") != "canonical_workflow_runtime":
                failures.append("plays:wrong_execution_authority")
            for item in payload.get("plays") or []:
                play = item.get("play") or {}
                readiness = item.get("readiness") or {}
                if play.get("executable") is not False:
                    failures.append(f'plays:{play.get("key")}:executable_not_false')
                # Read endpoint is intentionally unable to grant policy authorization.
                if readiness.get("act_within_policy_ready") is True:
                    failures.append(f'plays:{play.get("key")}:policy_not_fail_closed')

    health = next((p.get("payload") for p in probes if p["path"] == "/health"), {})
    report = {
        "at": datetime.now(timezone.utc).isoformat(),
        "backend_url": BASE,
        "org_id": org_id,
        "environment": environment,
        "git_sha": health.get("git_sha") if isinstance(health, dict) else None,
        "mutation": False,
        "paths": probes,
        "failures": failures,
        "pass": not failures,
        "claim": (
            "PASS — Plays readiness and observe routes are live and non-destructive"
            if not failures
            else "FAIL — one or more read-only Plays live gates failed"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("git_sha", "mutation", "failures", "pass", "claim")}, indent=2))
    print("WROTE", OUT)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
