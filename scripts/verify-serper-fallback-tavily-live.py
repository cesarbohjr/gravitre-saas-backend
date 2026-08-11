"""Phase 2: Force Serper failure → confirm visible Tavily fallback + metered provider=tavily."""
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
    # Safest real failure: invalid Serper key while keeping real Tavily
    os.environ["WEB_RESEARCH_PROVIDER"] = "serper"
    os.environ["WEB_RESEARCH_FALLBACK_TAVILY"] = "true"
    os.environ["SERPER_API_KEY"] = "invalid-serper-key-sta341-fallback-test"

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    from app.billing.service import get_supabase_client
    from app.services.web_research import search_web
    from gravitre_test_client import resolve_test_actor
    from isolated_conversation_org import DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID

    org_id, _actor, _email = resolve_test_actor()
    org_id = os.environ.get("OAUTH_SMOKE_ORG_ID") or DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID or org_id
    client = get_supabase_client(settings)

    query = f"STA-341 fallback smoke {datetime.now(timezone.utc).strftime('%H%M%S')}: What is CAN-SPAM?"
    ext = await search_web(query, settings=settings, max_results=3, org_id=org_id, client=client)

    rows = (
        client.table("usage_records")
        .select("recorded_at, metadata")
        .eq("org_id", org_id)
        .eq("metric_type", "research_lookups")
        .order("recorded_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    meta = rows[0].get("metadata") if rows and isinstance(rows[0].get("metadata"), dict) else {}

    report = {
        "record": "serper_fallback_tavily_live",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "method": "invalid SERPER_API_KEY forces primary http error → Tavily",
        "external_search": {
            "provider": ext.get("provider"),
            "fallback_from": ext.get("fallback_from"),
            "fallback_reason": ext.get("fallback_reason"),
            "totalResults": ext.get("totalResults"),
            "error": ext.get("error"),
        },
        "usage_metadata": meta,
        "railway_git_commit_sha": os.environ.get("RAILWAY_GIT_COMMIT_SHA") or "unknown",
    }
    ok = (
        ext.get("provider") == "tavily"
        and ext.get("fallback_from") == "serper"
        and int(ext.get("totalResults") or 0) > 0
        and meta.get("provider") == "tavily"
        and meta.get("fallback_from") == "serper"
    )
    report["verdict"] = (
        "PASS — Tavily fallback fired, logged via fallback_from, metered provider=tavily"
        if ok
        else "FAIL — fallback path incorrect"
    )
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    out = ROOT / "docs/delivery/serper-fallback-tavily-live.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
