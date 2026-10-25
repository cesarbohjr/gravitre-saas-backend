"""Durable tenant-isolated, read-only initial intelligence sweep worker.

This first stage inspects *verified integration telemetry*, not CRM financial
or customer records. Unsupported historical reads are reported as limitations,
never manufactured as business conclusions. No tool invokes or writes to apps.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import os
from typing import Any

from app.config import Settings, get_settings
from app.services.recommendation_heuristics_service import (
    build_heuristic_recommendations, load_connected_connectors, load_usage_by_connector,
)
from app.workflows.repository import get_supabase_client

MAX_SWEEPS_PER_TICK = 5
MAX_RECOMMENDATIONS = 20


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def assessment_for_org(client: Any, org_id: str) -> dict[str, Any]:
    """Never infer account value or causality from a connector's presence."""
    connected = load_connected_connectors(client, org_id)
    usable = [c for c in connected if c.get("executable")]
    vendors = sorted({str(c["vendor"]) for c in usable})
    usage = load_usage_by_connector(client, org_id)
    advisory = build_heuristic_recommendations(
        connected_connectors=connected,
        usage_by_connector=usage,
    )
    findings = []
    for item in usable:
        vendor = str(item["vendor"])
        invocations = usage.get(vendor)
        if invocations is None:
            continue
        findings.append({
            "id": "usage:" + vendor,
            "kind": "connector_usage",
            "title": vendor + " activity measured",
            "description": f"{invocations} recorded tool invocations over the telemetry window.",
            "sources": [{"kind": "audit_events", "vendor": vendor}],
            "confidence": None,
            "confidence_source": "measured_usage_telemetry",
            "lookback_days": 30,
            "business_impact": None,
            "advisory_only": True,
        })
    return {
        "analysis_type": "integration_telemetry_only",
        "coverage_verified": False,
        "comprehensive": False,
        "connectors": vendors,
        "insights": findings[:MAX_RECOMMENDATIONS],
        "recommendations": list(advisory.get("recommendations") or [])[:MAX_RECOMMENDATIONS],
        "outcomes": [],
        "actions": [],
        "limitations": [
            "Historical provider backfill not performed by this worker.",
            "Cross-department business facts, causation, and monetary impact not inferred.",
            "Usage telemetry does not prove that every provider data scope is authorized.",
        ],
        "generated_at": _timestamp(),
        "advisory_only": True,
    }


def process_queued_sweep(client: Any, row: dict[str, Any]) -> dict[str, Any]:
    """Claim with status CAS and enforce explicit tenant constraints on all writes."""
    org_id, sweep_id = str(row["org_id"]), str(row["id"])
    claim = (client.table("intelligence_overview_sweeps")
             .update({"status": "running", "started_at": _timestamp()})
             .eq("org_id", org_id).eq("id", sweep_id)
             .eq("status", "queued").execute())
    if not claim.data:
        return {"id": sweep_id, "status": "already_claimed"}
    try:
        results = assessment_for_org(client, org_id)
        update = {"status": "partial", "results": results, "completed_at": _timestamp()}
        (client.table("intelligence_overview_sweeps").update(update)
         .eq("org_id", org_id).eq("id", sweep_id).eq("status", "running").execute())
        return {"id": sweep_id, "status": "partial", "analysis_type": "integration_telemetry_only"}
    except Exception:
        # Never log raw provider records or internal exception details.
        (client.table("intelligence_overview_sweeps")
         .update({"status": "failed", "error_code": "assessment_failed", "completed_at": _timestamp()})
         .eq("org_id", org_id).eq("id", sweep_id).eq("status", "running").execute())
        return {"id": sweep_id, "status": "failed"}


def recover_stale_sweeps(client: Any, *, max_age_minutes: int = 30) -> int:
    """Fail interrupted claims so a crashed worker never leaves an endless spinner.

    A retry is a new, explicitly-requested run; no hidden repeated provider reads.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).isoformat()
    rows = (client.table("intelligence_overview_sweeps")
            .select("id,org_id,status,started_at")
            .eq("status", "running").lt("started_at", cutoff)
            .limit(MAX_SWEEPS_PER_TICK).execute())
    recovered = 0
    for row in list(rows.data or []):
        result = (client.table("intelligence_overview_sweeps")
                  .update({"status": "failed", "error_code": "worker_interrupted",
                           "completed_at": _timestamp()})
                  .eq("org_id", str(row["org_id"])).eq("id", str(row["id"]))
                  .eq("status", "running").execute())
        recovered += bool(result.data)
    return recovered


def process_sweep_batch(settings: Settings | None = None) -> list[dict[str, Any]]:
    client = get_supabase_client(settings or get_settings())
    recover_stale_sweeps(client)
    rows = (client.table("intelligence_overview_sweeps")
            .select("id,org_id,status,created_at")
            .eq("status", "queued").order("created_at").limit(MAX_SWEEPS_PER_TICK).execute())
    return [process_queued_sweep(client, row) for row in list(rows.data or [])]


async def _loop(settings: Settings) -> None:
    while True:
        try:
            await asyncio.to_thread(process_sweep_batch, settings)
        except Exception:
            # Database unavailable: no fake success, next poll will retry.
            pass
        await asyncio.sleep(60)


def start_overview_sweep_worker() -> asyncio.Task | None:
    # Explicitly opt-in only after migration and controlled acceptance tests.
    if os.getenv("INTELLIGENCE_OVERVIEW_SWEEP_WORKER_ENABLED", "").lower() not in {"1", "true"}:
        return None
    return asyncio.create_task(_loop(get_settings()))


async def stop_overview_sweep_worker(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
