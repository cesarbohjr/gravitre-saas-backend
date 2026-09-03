#!/usr/bin/env python3
"""Live proof: joined run observability console against tip API."""
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "delivery" / "run-observability-console-live.json"
BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
sys.path.insert(0, str(ROOT / "scripts"))
from isolated_conversation_org import resolve_isolated_conversation_actor  # noqa: E402


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ROOT / "backend" / ".env", ROOT / "backend" / ".env.operator.local"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                raw = line.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                key, _, val = raw.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and val:
                    merged[key] = val
    return merged


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Content-Type": "application/json",
    }

    report: dict = {
        "probe": "run_observability_console_live",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "org_id": org_id,
    }

    with httpx.Client(timeout=90.0) as client:
        health = client.get(f"{BASE}/health").json()
        report["api_git_sha"] = health.get("git_sha")

        runs = client.get(f"{BASE}/api/runs", headers=headers, params={"limit": 5}).json()
        items = runs.get("runs") or runs.get("items") or runs.get("data") or []
        if isinstance(runs, list):
            items = runs
        report["runs_listed"] = len(items) if isinstance(items, list) else 0
        if not items:
            report["verdict"] = "INCONCLUSIVE"
            report["reason"] = "no runs in isolated org"
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 2

        run_id = str(items[0].get("id") or items[0].get("runId") or "")
        report["run_id"] = run_id
        obs = client.get(f"{BASE}/api/runs/{run_id}/observability", headers=headers)
        report["http_status"] = obs.status_code
        if obs.status_code != 200:
            report["verdict"] = "FAIL"
            report["body"] = obs.text[:500]
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return 1

        dto = obs.json()
        required = [
            "runId",
            "intent",
            "contextSources",
            "ragQueries",
            "toolsCalled",
            "agentHandoffs",
            "actionsTaken",
            "approvalsRequired",
            "finalResult",
            "replay",
            "sources",
        ]
        missing = [k for k in required if k not in dto]
        # Never expose private CoT keys in joined payload.
        blob = json.dumps(dto)
        cot_leak = any(tok in blob for tok in ('"chain_of_thought"', '"raw_prompt"', '"system_prompt"'))
        report["missing_keys"] = missing
        report["cot_leak"] = cot_leak
        report["audit_event_count"] = dto.get("auditEventCount")
        report["replay_len"] = len(dto.get("replay") or [])
        report["sources"] = dto.get("sources")
        report["final_status"] = (dto.get("finalResult") or {}).get("status")
        report["verdict"] = "PASS" if not missing and not cot_leak else "FAIL"

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
