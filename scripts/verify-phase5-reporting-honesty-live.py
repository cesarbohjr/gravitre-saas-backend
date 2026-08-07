#!/usr/bin/env python3
"""Phase 5 live: reporting honesty audit on tip-matched API."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "delivery" / "phase5-reporting-insights-honesty-live.json"
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
        "probe": "phase5_reporting_honesty_live",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "org_id": org_id,
    }

    with httpx.Client(timeout=90.0) as client:
        health = client.get(f"{BASE}/health").json()
        report["api_git_sha"] = health.get("git_sha")

        audit = client.get(f"{BASE}/api/reporting/honesty-audit", headers=headers)
        report["audit_http"] = audit.status_code
        if audit.status_code != 200:
            report["verdict"] = f"FAIL — honesty-audit http {audit.status_code}"
            report["audit_body"] = audit.text[:500]
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"]}, indent=2))
            return 1
        body = audit.json()
        report["audit_verdict"] = body.get("verdict")
        report["surface_count"] = len(body.get("surfaces") or [])
        report["summary"] = body.get("summary")
        report["roi_placeholders"] = body.get("roi_placeholders")

        metrics = client.get(f"{BASE}/api/metrics/overview?range=7d", headers=headers)
        report["metrics_http"] = metrics.status_code
        if metrics.status_code == 200:
            m = metrics.json()
            report["metrics_honesty"] = m.get("honesty")
            report["metrics_success_rate"] = m.get("successRate")
        else:
            report["metrics_error"] = metrics.text[:300]

        # Confirm invalid ranges still rejected (honesty of API contract).
        bad = client.get(f"{BASE}/api/metrics/overview?range=24h", headers=headers)
        report["metrics_24h_http"] = bad.status_code

    ok = (
        report.get("audit_verdict") in {"PASS", "PASS_WITH_WARNINGS"}
        and int(report.get("surface_count") or 0) >= 10
        and report.get("metrics_http") == 200
        and isinstance(report.get("metrics_honesty"), dict)
        and report["metrics_honesty"].get("successRateProvenance") == "live_runs"
        and report.get("metrics_24h_http") == 400
        and all(
            (p or {}).get("provenance") == "not_configured"
            for p in (report.get("roi_placeholders") or [])
        )
    )
    report["verdict"] = (
        f"PASS — reporting honesty @ {str(report.get('api_git_sha') or '')[:8]}"
        if ok
        else f"FAIL — audit={report.get('audit_verdict')} metrics={report.get('metrics_http')}"
    )
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "api_git_sha": report.get("api_git_sha"),
                "audit_verdict": report.get("audit_verdict"),
                "surface_count": report.get("surface_count"),
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
