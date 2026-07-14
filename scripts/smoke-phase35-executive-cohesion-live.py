#!/usr/bin/env python3
"""Phase 3.5 live smoke: Executive pack cohesion — KPIs, result_url, notifications.

Writes docs/delivery/phase35-executive-cohesion-live.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "phase35-executive-cohesion-live.json"
PACK = "executive-intelligence-pack"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(p).items() if v})
        except UnicodeDecodeError:
            text = p.read_bytes().decode("utf-8", errors="replace")
            for line in text.splitlines():
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and val:
                    merged[key] = val
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.intelligence_packs.shared.kpis import pack_kpi_summary
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)

    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    before_notifs = (
        sb.table("notifications")
        .select("id", count="exact")
        .eq("org_id", ORG)
        .eq("user_id", ACTOR)
        .eq("type", "task_completed")
        .limit(1)
        .execute()
    )
    notif_before = int(getattr(before_notifs, "count", None) or 0)

    ctx = ToolContext(settings=settings, client=sb, org_id=ORG, actor_id=ACTOR)
    fred = invoke_tool(ctx, "fred.series.get", {"series_id": "GDP"})
    sec = invoke_tool(ctx, "sec_edgar.filings.search", {"query": "Microsoft"})

    fred_url = (fred.data or {}).get("result_url")
    sec_url = (sec.data or {}).get("result_url")

    after_notifs = (
        sb.table("notifications")
        .select("id,title,url,type", count="exact")
        .eq("org_id", ORG)
        .eq("user_id", ACTOR)
        .eq("type", "task_completed")
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )
    notif_after = int(getattr(after_notifs, "count", None) or 0)
    recent = after_notifs.data or []

    kpis = pack_kpi_summary(sb, org_id=ORG, pack_id=PACK)

    # UI cohesion: shared component is in reports page source (static check)
    reports = (REPO / "apps" / "web" / "app" / "intelligence" / "reports" / "page.tsx").read_text(
        encoding="utf-8"
    )
    panel_src = (REPO / "apps" / "web" / "components" / "marketplace" / "pack-kpi-panel.tsx").read_text(
        encoding="utf-8"
    )
    ui_ok = (
        'PackKpiPanel' in reports
        and 'packId="executive-intelligence-pack"' in reports
        and 'data-testid="pack-kpi-panel"' in panel_src
    )

    result_url_ok = (
        fred.success
        and sec.success
        and isinstance(fred_url, str)
        and fred_url.startswith("https://")
        and isinstance(sec_url, str)
        and sec_url.startswith("https://")
    )
    notif_ok = notif_after > notif_before and any(
        "FRED" in str(r.get("title") or "") or "SEC" in str(r.get("title") or "") for r in recent
    )
    kpi_ok = bool(kpis.get("signalsCount", 0) >= 1 or kpis.get("entitiesCount", 0) >= 1)

    passed = result_url_ok and notif_ok and kpi_ok and ui_ok

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "pack_id": PACK,
        "checks": {
            "result_url": {
                "pass": result_url_ok,
                "fred": fred_url,
                "sec": sec_url,
                "fred_success": fred.success,
                "sec_success": sec.success,
            },
            "notifications": {
                "pass": notif_ok,
                "count_before": notif_before,
                "count_after": notif_after,
                "recent_titles": [r.get("title") for r in recent[:3]],
                "path": "emit_notification(task_completed)",
            },
            "pack_kpis": {
                "pass": kpi_ok,
                "summary": {
                    k: kpis.get(k)
                    for k in (
                        "installed",
                        "signalsCount",
                        "entitiesCount",
                        "cacheTouches",
                        "agentCount",
                        "workflowCount",
                    )
                },
                "api": f"GET /api/intelligence-packs/{PACK}/kpis",
            },
            "shared_dashboard_component": {
                "pass": ui_ok,
                "component": "apps/web/components/marketplace/pack-kpi-panel.tsx",
                "mounted_on": "apps/web/app/intelligence/reports/page.tsx (Executive tab)",
            },
        },
        "note": (
            "Phase 3.5 Executive cohesion: shared PackKpiPanel + result_url on "
            "fred/sec invoke + emit_notification on pack source success."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "checks": {k: v["pass"] for k, v in artifact["checks"].items()}}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
