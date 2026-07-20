#!/usr/bin/env python3
"""Live smoke: internet research enablement (Google grounding + metering + volume monitor).

Requires prod/staging credentials in backend/.env.operator.local or env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, API_PUBLIC_URL, operator JWT

Usage:
  python3 scripts/smoke-internet-research-live.py --json docs/delivery/internet-research-live-latest.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import dotenv_values


def _load_env_files() -> None:
    """Load backend env files with encoding fallback (Windows cp1252 operator files)."""
    for path in (ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"):
        if not path.is_file():
            continue
        values: dict[str, str | None] = {}
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                values = dotenv_values(path, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        for key, value in values.items():
            if value and key not in os.environ:
                os.environ[key] = value


_load_env_files()


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    parser.add_argument("--org-id", default=os.getenv("OAUTH_SMOKE_ORG_ID", ""))
    args = parser.parse_args()

    from app.config import get_settings
    from app.services.web_research import search_web
    from app.billing.service import get_supabase_client
    from app.services.grounding_volume_monitor import (
        check_org_grounding_circuit,
        get_platform_grounding_status,
        org_hourly_circuit_limit,
    )

    settings = get_settings()
    client = get_supabase_client(settings)
    org_id = args.org_id.strip()
    if not org_id:
        print("OAUTH_SMOKE_ORG_ID required", file=sys.stderr)
        return 2

    report: dict = {
        "record": "internet_research_live_smoke",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "internet_research_enabled": bool(settings.internet_research_enabled),
        "web_research_provider": settings.web_research_provider,
        "grounding_org_hourly_circuit_limit": org_hourly_circuit_limit(settings),
    }

    circuit_before = check_org_grounding_circuit(client, org_id, settings)
    report["org_hourly_circuit_before"] = circuit_before

    # External query (should run internet when flag on + scope)
    ext = await search_web(
        "What is the current US federal funds rate?",
        settings=settings,
        max_results=3,
        org_id=org_id,
        client=client,
    )
    report["external_search"] = {
        "totalResults": ext.get("totalResults"),
        "provider": ext.get("provider"),
        "has_urls": any(r.get("url") for r in (ext.get("results") or [])),
        "error": ext.get("error"),
        "query_sent": ext.get("query_sent"),
        "context_stripped": ext.get("context_stripped"),
        "was_truncated": ext.get("was_truncated"),
        "circuit_breaker": ext.get("circuit_breaker"),
    }

    platform = get_platform_grounding_status(client, settings)
    report["grounding_volume"] = platform
    report["org_hourly_circuit_after"] = check_org_grounding_circuit(client, org_id, settings)

    org_daily = (
        client.table("org_research_lookup_daily")
        .select("lookup_count, usage_date")
        .eq("org_id", org_id)
        .order("usage_date", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    report["org_research_lookup_daily_latest"] = org_daily

    usage = (
        client.table("usage_records")
        .select("metric_type, quantity, metadata")
        .eq("org_id", org_id)
        .eq("metric_type", "research_lookups")
        .order("recorded_at", desc=True)
        .limit(3)
        .execute()
        .data
        or []
    )
    report["recent_research_lookup_usage"] = usage

    report["verdict"] = "NOT RUN"
    if not settings.internet_research_enabled:
        report["verdict"] = "PARTIAL — INTERNET_RESEARCH_ENABLED off; provider smoke only"
    elif report["external_search"].get("has_urls") and report["external_search"].get("totalResults", 0) > 0:
        report["verdict"] = "PASS — live grounding returned cited URLs"
    else:
        report["verdict"] = "INCONCLUSIVE — check credentials and flag"

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
