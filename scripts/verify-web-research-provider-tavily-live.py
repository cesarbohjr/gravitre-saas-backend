#!/usr/bin/env python3
"""Step 1: Prove prod WEB_RESEARCH_PROVIDER=tavily is a direct path (no Google fallback).

Prefer: `railway run --service gravitre-saas-backend python scripts/verify-web-research-provider-tavily-live.py`

That injects Railway env so Settings match production.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))


def _load_env_files() -> None:
    from dotenv import dotenv_values

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


async def main() -> int:
    _load_env_files()
    # Clear Settings cache so Railway-injected env wins after dotenv fill-ins.
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    from app.billing.service import get_supabase_client
    from app.services.web_research import search_web
    from gravitre_test_client import resolve_test_actor
    from isolated_conversation_org import DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID

    org_id, _actor, _email = resolve_test_actor()
    # Prefer isolated smoke org for metering proof
    org_id = os.environ.get("OAUTH_SMOKE_ORG_ID") or DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID or org_id

    provider = (settings.web_research_provider or "").strip().lower()
    report: dict = {
        "record": "web_research_provider_tavily_live",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "railway_git_commit_sha": os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_SHA")
        or "unknown",
        "settings": {
            "web_research_provider": provider,
            "web_research_fallback_tavily": bool(settings.web_research_fallback_tavily),
            "internet_research_enabled": bool(settings.internet_research_enabled),
            "tavily_configured": bool((settings.tavily_api_key or "").strip()),
            "gemini_configured": bool((getattr(settings, "gemini_api_key", None) or "").strip()),
        },
        "path_analysis": {
            "google_primary_block_entered": provider == "google",
            "direct_tavily_path": provider == "tavily",
            "note": "When provider=tavily, web_research.search_web skips Google entirely (no fallback event).",
        },
        "org_id": org_id,
    }

    if provider != "tavily":
        report["verdict"] = f"FAIL — web_research_provider={provider!r}, expected 'tavily'"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        out = ROOT / "docs" / "delivery" / "web-research-provider-tavily-live.json"
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    client = get_supabase_client(settings)
    query = "What is the current US federal funds rate?"
    ext = await search_web(
        query,
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
    }

    usage = (
        client.table("usage_records")
        .select("metric_type, quantity, metadata, recorded_at")
        .eq("org_id", org_id)
        .eq("metric_type", "research_lookups")
        .order("recorded_at", desc=True)
        .limit(3)
        .execute()
        .data
        or []
    )
    report["recent_usage_records"] = usage
    latest_provider = None
    if usage:
        meta = usage[0].get("metadata") or {}
        latest_provider = meta.get("provider")
    report["latest_metered_provider"] = latest_provider

    ok = (
        provider == "tavily"
        and ext.get("provider") == "tavily"
        and int(ext.get("totalResults") or 0) > 0
        and not report["path_analysis"]["google_primary_block_entered"]
        and latest_provider == "tavily"
    )
    report["verdict"] = (
        "PASS — direct tavily path; metered provider=tavily; google block not entered"
        if ok
        else "FAIL — see fields"
    )
    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    out = ROOT / "docs" / "delivery" / "web-research-provider-tavily-live.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
