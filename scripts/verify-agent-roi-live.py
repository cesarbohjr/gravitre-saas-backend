#!/usr/bin/env python3
"""Live verify: agent ROI honesty against a real org's usage data."""
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
OUT = ROOT / "docs" / "delivery" / "agent-roi-live.json"
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
    # GitHub Actions supplies protected values in the process environment.
    # Prefer those over local operator files; never include values in reports.
    merged.update({key: os.environ[key] for key in (
        "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET",
    ) if os.environ.get(key)})
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
        "probe": "agent_roi_live",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "org_id": org_id,
    }

    with httpx.Client(timeout=90.0) as client:
        health = client.get(f"{BASE}/health").json()
        report["api_git_sha"] = health.get("git_sha")

        roi = client.get(f"{BASE}/api/enterprise/agent-roi?period_days=30", headers=headers)
        report["roi_http"] = roi.status_code
        if roi.status_code != 200:
            report["verdict"] = f"FAIL — agent-roi http {roi.status_code}"
            report["roi_body"] = roi.text[:800]
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"]}, indent=2))
            return 1

        body = roi.json()
        report["period_days"] = body.get("periodDays")
        report["agent_count"] = len(body.get("agents") or [])
        report["methodology_present"] = bool(body.get("methodology"))
        totals = body.get("orgTotals") or {}
        report["org_totals"] = {
            k: {"value": (totals.get(k) or {}).get("value"), "provenance": (totals.get(k) or {}).get("provenance")}
            for k in (
                "tasksCompleted",
                "actionsExecuted",
                "agentCostUsd",
                "estimatedHoursSaved",
                "estimatedLaborValueUsd",
                "revenueInfluencedUsd",
                "roiMultiple",
            )
        }
        report["honesty"] = body.get("honesty")
        report["labor"] = body.get("laborUsdPerHour")

        # Cross-check measured cost against model_calls for this org (last 30d window from response).
        start = body.get("periodStart")
        end = body.get("periodEnd")
        # Match the API's paginated evidence window; a single .limit(5000)
        # silently omitted calls and produced a false cost mismatch.
        mc: list[dict] = []
        offset = 0
        page_size = 500
        while offset < 10_000:
            batch = (
                sb.table("model_calls")
                .select("id,cost_usd,agent_id")
                .eq("org_id", org_id)
                .gte("created_at", start)
                .lt("created_at", end)
                .order("id")
                .range(offset, offset + page_size - 1)
                .execute()
                .data
                or []
            )
            mc.extend(batch)
            offset += len(batch)
            if len(batch) < page_size:
                break
        if len(mc) >= 10_000:
            report["verdict"] = "FAIL — cost evidence exceeds verified pagination boundary"
            report["model_call_count"] = len(mc)
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return 1
        measured_sum = round(sum(float(r.get("cost_usd") or 0) for r in mc), 6)
        api_cost = float((totals.get("agentCostUsd") or {}).get("value") or 0)
        report["model_calls_sum_usd"] = measured_sum
        report["api_cost_usd"] = api_cost
        report["cost_match"] = abs(measured_sum - api_cost) < 0.0001

        # Sample first agent row honesty if present
        agents = body.get("agents") or []
        if agents:
            sample = agents[0]
            report["sample_agent"] = {
                "agentId": sample.get("agentId"),
                "agentName": sample.get("agentName"),
                "cost_provenance": (sample.get("agentCostUsd") or {}).get("provenance"),
                "hours_provenance": (sample.get("estimatedHoursSaved") or {}).get("provenance"),
                "labor_provenance": (sample.get("estimatedLaborValueUsd") or {}).get("provenance"),
                "revenue_provenance": (sample.get("revenueInfluencedUsd") or {}).get("provenance"),
                "roi_provenance": (sample.get("roiMultiple") or {}).get("provenance"),
            }

    totals = report["org_totals"]
    checks = {
        "roi_http": report["roi_http"] == 200,
        "methodology_present": report["methodology_present"],
        "model_cost_matches_ledger": report["cost_match"],
        "agent_cost_measured": totals["agentCostUsd"]["provenance"] == "measured",
        "tasks_operational": totals["tasksCompleted"]["provenance"] == "operational",
        "hours_estimated": totals["estimatedHoursSaved"]["provenance"] == "estimate",
        "labor_estimated": totals["estimatedLaborValueUsd"]["provenance"] == "estimate",
        "revenue_provenance": totals["revenueInfluencedUsd"]["provenance"] in {"not_configured", "measured"},
        "unconfigured_revenue_is_null": (
            totals["revenueInfluencedUsd"]["provenance"] != "not_configured"
            or totals["revenueInfluencedUsd"]["value"] is None
        ),
        "module_c_honesty": (report.get("honesty") or {}).get("moduleC") is True,
        "sta286_honesty": (report.get("honesty") or {}).get("sta286") is True,
        "roi_multiple_provenance": (
            totals["roiMultiple"]["provenance"] == "estimate"
            if totals["roiMultiple"]["value"] is not None
            else totals["roiMultiple"]["provenance"] in {"insufficient_data", "estimate"}
        ),
    }
    report["checks"] = checks
    report["failed_checks"] = [name for name, passed in checks.items() if not passed]
    ok = all(checks.values())

    report["verdict"] = (
        "PASS — agent ROI honesty + measured cost match"
        if ok
        else "FAIL — agent ROI honesty or cost mismatch"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "api_git_sha": report.get("api_git_sha"), "failed_checks": report["failed_checks"], "out": str(OUT)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
