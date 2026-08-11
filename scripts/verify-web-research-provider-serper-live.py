"""Phase 2: Prove prod WEB_RESEARCH_PROVIDER=serper meters provider=serper (no fallback)."""
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
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    from app.billing.service import get_supabase_client
    from app.services.web_research import search_web
    from gravitre_test_client import resolve_test_actor
    from isolated_conversation_org import DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID

    org_id, _actor, _email = resolve_test_actor()
    org_id = os.environ.get("OAUTH_SMOKE_ORG_ID") or DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID or org_id

    provider = (settings.web_research_provider or "").strip().lower()
    report: dict = {
        "record": "web_research_provider_serper_live",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "railway_git_commit_sha": os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or os.environ.get("GIT_SHA")
        or "unknown",
        "settings": {
            "web_research_provider": provider,
            "web_research_fallback_tavily": bool(settings.web_research_fallback_tavily),
            "serper_configured": bool((settings.serper_api_key or "").strip()),
            "tavily_configured": bool((settings.tavily_api_key or "").strip()),
        },
        "path_analysis": {
            "serper_primary_block_entered": provider == "serper",
            "direct_tavily_path": provider == "tavily",
        },
        "org_id": org_id,
    }

    if provider != "serper":
        report["verdict"] = f"FAIL — web_research_provider={provider!r}, expected 'serper'"
        out = ROOT / "docs/delivery/web-research-provider-serper-live.json"
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    client = get_supabase_client(settings)
    query = f"STA-341 serper primary smoke {datetime.now(timezone.utc).strftime('%H%M%S')}: US federal funds rate"
    ext = await search_web(query, settings=settings, max_results=3, org_id=org_id, client=client)
    report["external_search"] = {
        "totalResults": ext.get("totalResults"),
        "provider": ext.get("provider"),
        "fallback_from": ext.get("fallback_from"),
        "fallback_reason": ext.get("fallback_reason"),
        "has_urls": any(r.get("url") for r in (ext.get("results") or [])),
        "error": ext.get("error"),
    }

    # Latest usage_records row for this org
    rows = (
        client.table("usage_records")
        .select("recorded_at, metadata, quantity")
        .eq("org_id", org_id)
        .eq("metric_type", "research_lookups")
        .order("recorded_at", desc=True)
        .limit(3)
        .execute()
        .data
        or []
    )
    report["usage_records_latest"] = rows
    metered_provider = None
    if rows:
        meta = rows[0].get("metadata") if isinstance(rows[0].get("metadata"), dict) else {}
        metered_provider = meta.get("provider")
    report["metered_provider"] = metered_provider

    ok = (
        ext.get("provider") == "serper"
        and not ext.get("fallback_from")
        and int(ext.get("totalResults") or 0) > 0
        and metered_provider == "serper"
    )
    report["verdict"] = (
        "PASS — Serper primary served + metered provider=serper, no fallback"
        if ok
        else "FAIL — expected serper primary without fallback"
    )
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    out = ROOT / "docs/delivery/web-research-provider-serper-live.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
