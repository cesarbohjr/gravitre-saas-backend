"""Sanity test: intelligence outcome events (Supabase + ClickHouse + admin APIs).

Flow:
  1. Create a test optimization suggestion (recommendation_created)
  2. Dismiss it (recommendation_rejected)
  3. Verify rows in Supabase intelligence_outcome_events
  4. Verify admin /outcomes and /training-readiness
  5. Verify ClickHouse mirror when configured

Usage:
  npm run dev:backend   # separate terminal
  python scripts/sanity-intelligence-outcomes.py
  BACKEND_URL=https://api.gravitre.app python scripts/sanity-intelligence-outcomes.py
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

_spec = importlib.util.spec_from_file_location(
    "smoke_ai_production", REPO / "scripts" / "smoke-ai-production.py"
)
smoke = importlib.util.module_from_spec(_spec)
sys.modules["smoke_ai_production"] = smoke
_spec.loader.exec_module(smoke)

API_BASE = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
SANITY_TAG = f"sanity-{uuid.uuid4().hex[:8]}"


def _fail(message: str) -> None:
    print(json.dumps({"status": "fail", "error": message}, indent=2))
    raise SystemExit(1)


def _pass(results: dict[str, Any]) -> None:
    print(json.dumps({"status": "pass", **results}, indent=2))


def _json_get(path: str, token: str, org_id: str) -> dict[str, Any]:
    smoke.API_BASE = API_BASE
    return smoke._request("GET", path, token, org_id)


def _json_post(path: str, token: str, org_id: str, body: dict | None = None) -> dict[str, Any]:
    smoke.API_BASE = API_BASE
    return smoke._request("POST", path, token, org_id, body)


async def _verify_clickhouse(org_id: str, recommendation_id: str) -> dict[str, Any]:
    from app.services.clickhouse_service import get_clickhouse_service

    ch = get_clickhouse_service()
    if not ch.is_available():
        return {"available": False, "pass": True, "note": "CLICKHOUSE_HOST unset — Postgres is source of truth"}

    rows = await ch.query(
        """
        SELECT outcome_event, entity_id, org_id
        FROM gravitre.intelligence_outcome_events
        WHERE org_id = {org_id:String}
          AND entity_id = {entity_id:String}
        ORDER BY created_at DESC
        LIMIT 10
        """,
        {"org_id": org_id, "entity_id": recommendation_id},
    )
    events = [str(r.get("outcome_event") or "") for r in rows]
    return {
        "available": True,
        "pass": "recommendation_created" in events and "recommendation_rejected" in events,
        "events": events,
        "row_count": len(rows),
    }


async def _create_test_suggestion(org_id: str) -> str:
    from app.services.optimization_suggestion_service import get_optimization_suggestion_service

    service = get_optimization_suggestion_service()
    row = await service._insert_suggestion(
        org_id,
        target_entity_type="sanity_test",
        target_entity_id=SANITY_TAG,
        suggestion_type="sanity_outcome_test",
        evidence={"source": "sanity-intelligence-outcomes.py", "tag": SANITY_TAG},
        suggested_action=f"Sanity test recommendation ({SANITY_TAG}) — dismiss to verify outcome tracking.",
        estimated_impact="low",
    )
    suggestion_id = str(row.get("id") or "")
    if not suggestion_id:
        _fail("Failed to create test optimization suggestion")
    return suggestion_id


async def _fetch_supabase_events(org_id: str, recommendation_id: str) -> list[dict[str, Any]]:
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(get_settings())
    result = (
        client.table("intelligence_outcome_events")
        .select("outcome_event, recommendation_id, entity_id, created_at")
        .eq("org_id", org_id)
        .eq("recommendation_id", recommendation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


async def main() -> None:
    env = smoke._load_env()
    for key, value in env.items():
        os.environ.setdefault(key, value)
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_ANON_KEY"):
        if env.get(key):
            os.environ.setdefault(key, env[key])

    org_id, user_id, email = smoke._admin_org(env)
    token = smoke._mint_token(env, user_id, email)

    # Verify migration / table reachable
    try:
        table_check = smoke._supabase_client(env).table("intelligence_outcome_events").select("id").limit(1).execute()
        migration_ok = table_check is not None
    except Exception as exc:  # noqa: BLE001
        _fail(f"intelligence_outcome_events table not reachable: {exc}")

    suggestion_id = await _create_test_suggestion(org_id)
    await asyncio.sleep(0.5)

    created_rows = await _fetch_supabase_events(org_id, suggestion_id)
    if not any(r.get("outcome_event") == "recommendation_created" for r in created_rows):
        _fail(
            f"recommendation_created not found in Supabase for {suggestion_id}: "
            f"{json.dumps(created_rows)}"
        )

    dismiss = _json_post(
        f"/api/admin/optimization-suggestions/{suggestion_id}/dismiss",
        token,
        org_id,
        {"reason": f"Sanity test reject ({SANITY_TAG})"},
    )
    if str(dismiss.get("status") or "") != "dismissed":
        _fail(f"Dismiss did not return dismissed status: {json.dumps(dismiss)[:500]}")

    await asyncio.sleep(1.0)
    all_rows = await _fetch_supabase_events(org_id, suggestion_id)
    event_types = [str(r.get("outcome_event") or "") for r in all_rows]
    if "recommendation_rejected" not in event_types:
        _fail(f"recommendation_rejected not found in Supabase: {event_types}")

    outcomes = _json_get("/api/admin/intelligence/outcomes?periodDays=7", token, org_id)
    by_event = outcomes.get("by_event_type") or {}
    admin_outcomes_ok = (
        isinstance(outcomes, dict)
        and "summary" in outcomes
        and int(by_event.get("recommendation_created") or 0) >= 1
        and int(by_event.get("recommendation_rejected") or 0) >= 1
    )

    training = _json_get("/api/admin/intelligence/training-readiness", token, org_id)
    training_ok = (
        isinstance(training, dict)
        and "by_model" in training
        and isinstance(training.get("by_model"), dict)
        and "orgs_ready_for_training" in training
    )

    clickhouse = await _verify_clickhouse(org_id, suggestion_id)

    results = {
        "org_id": org_id,
        "recommendation_id": suggestion_id,
        "sanity_tag": SANITY_TAG,
        "backend_url": API_BASE,
        "migration_table_ok": migration_ok,
        "supabase_events": event_types,
        "admin_outcomes_ok": admin_outcomes_ok,
        "admin_outcomes_summary": outcomes.get("summary"),
        "admin_by_event_type_sample": {
            k: by_event[k]
            for k in ("recommendation_created", "recommendation_rejected")
            if k in by_event
        },
        "training_readiness_ok": training_ok,
        "training_readiness": {
            "orgs_ready_for_training": training.get("orgs_ready_for_training"),
            "recommended_next_training": training.get("recommended_next_training"),
        },
        "clickhouse": clickhouse,
    }

    if not admin_outcomes_ok:
        _fail(f"Admin outcomes summary missing expected events: {json.dumps(outcomes)[:800]}")
    if not training_ok:
        _fail(f"training-readiness response invalid: {json.dumps(training)[:800]}")
    if clickhouse.get("available") and not clickhouse.get("pass"):
        _fail(f"ClickHouse mirror missing events: {json.dumps(clickhouse)}")

    _pass(results)


if __name__ == "__main__":
    asyncio.run(main())
