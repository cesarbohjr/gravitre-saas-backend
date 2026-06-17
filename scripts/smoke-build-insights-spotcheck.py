"""Production spot-check for BUILD/INSIGHTS pages (audit, workflows, metrics, runs).

Uses the same auth pattern as smoke-ai-production.py against Railway prod.

Usage:
  python scripts/smoke-build-insights-spotcheck.py
  python scripts/smoke-build-insights-spotcheck.py --json docs/delivery/build-insights-spotcheck-latest.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load_smoke():
    name = "smoke_ai_production"
    spec = importlib.util.spec_from_file_location(
        name,
        REPO / "scripts" / "smoke-ai-production.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run_spotcheck() -> dict:
    smoke = _load_smoke()
    env = smoke._load_env()
    org_id, user_id, email = smoke._admin_org(env)
    token = smoke._mint_token(env, user_id, email)

    checks: list[dict] = []

    def check(name: str, method: str, path: str, summarize):
        try:
            data = smoke._request(method, path, token, org_id, timeout=30)
            checks.append(
                {
                    "check": name,
                    "status": "pass",
                    "http": 200,
                    "detail": summarize(data),
                }
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:240]
            checks.append(
                {
                    "check": name,
                    "status": "fail",
                    "http": exc.code,
                    "detail": body,
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append({"check": name, "status": "fail", "detail": str(exc)})

    check(
        "audit_logs",
        "GET",
        "/api/audit?limit=5",
        lambda d: {
            "total": d.get("total"),
            "logs_count": len(d.get("logs") or []),
            "hasMore": d.get("hasMore"),
        },
    )
    check(
        "workflows_stats",
        "GET",
        "/api/workflows/stats",
        lambda d: {
            k: d.get(k)
            for k in (
                "overallSuccessRate",
                "totalRunsThisWeek",
                "activeWorkflows",
                "pausedWorkflows",
            )
            if k in d
        },
    )
    check(
        "metrics_overview",
        "GET",
        "/api/metrics/overview?range=7d",
        lambda d: {
            k: d.get(k)
            for k in ("totalRuns", "successRate", "recordsProcessed", "avgLatency")
            if k in d
        },
    )
    check(
        "metrics_insights",
        "GET",
        "/api/metrics/insights?range=7d",
        lambda d: {
            "insights_count": len(d.get("insights") or []),
            "generatedAt": d.get("generatedAt"),
        },
    )
    check(
        "weekly_throughput",
        "GET",
        "/api/metrics/weekly-throughput",
        lambda d: {
            "target": d.get("target"),
            "days_len": len(d.get("days") or []),
        },
    )
    check(
        "runs_list",
        "GET",
        "/api/runs?limit=10",
        lambda d: {
            "runs_count": len(d.get("runs") or []) if isinstance(d, dict) else len(d or []),
            "total": d.get("total") if isinstance(d, dict) else None,
        },
    )

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")

    return {
        "target": smoke.API_BASE,
        "appUrl": "https://gravitre.app",
        "orgId": org_id,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "summary": {"pass": passed, "fail": failed},
        "checks": checks,
        "uiNotes": [
            "Protected app routes redirect unauthenticated users to /login (expected).",
            "metrics/page.tsx still has display fallbacks (1,247 / 98.7% / 1.8M / 142ms) when API fields are null.",
            "audit/page.tsx uses empty fallbackData (does not mask errors with fake rows).",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_path", help="Write JSON report to path")
    args = parser.parse_args()

    report = run_spotcheck()
    text = json.dumps(report, indent=2)
    print(text)

    if args.json_path:
        out = REPO / args.json_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {out}", file=sys.stderr)

    return 0 if report["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
