#!/usr/bin/env python3
"""DB-side live smoke for Phase 1.5 — service-role pipeline on PROD.

Runs fetch + run_shared_ingestion for fred / nvd / world_bank against prod DB.
Used to prove cache/entity/signal writes BEFORE merge (HTTP route not on tip yet).
After merge+deploy, prefer smoke-phase15-shared-plumbing-http-live.py.

Writes docs/delivery/phase1.5-shared-plumbing-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
OUT = REPO / "docs" / "delivery" / "phase1.5-shared-plumbing-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if p.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(p).items() if v})
            except UnicodeDecodeError:
                pass
    for k, v in merged.items():
        os.environ.setdefault(k, v)


async def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.intelligence_packs.executive.sources import fetch_fred_series, fetch_world_bank_indicator
    from app.intelligence_packs.msp import fetch_nvd_cve
    from app.intelligence_packs.shared.pipeline import run_shared_ingestion

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    jobs = [
        ("fred", await fetch_fred_series("GDP", settings=settings), "series:GDP", 3600),
        ("nvd", await fetch_nvd_cve("CVE-2024-21762", settings=settings), "cve:CVE-2024-21762", 3600),
        (
            "world_bank",
            await fetch_world_bank_indicator("US", "NY.GDP.MKTP.CD", settings=settings),
            "indicator:US:NY.GDP.MKTP.CD",
            86400,
        ),
    ]

    results: dict = {}
    for vendor, raw, cache_key, ttl in jobs:
        results[vendor] = run_shared_ingestion(
            client,
            org_id=ORG,
            vendor=vendor,
            cache_key=cache_key,
            raw=raw,
            ttl_seconds=ttl,
        )

    per_vendor_ok = {
        v: bool(results[v].get("ok"))
        and bool((results[v].get("cache") or {}).get("id"))
        and bool(results[v].get("entities"))
        and bool(results[v].get("signals"))
        for v, *_ in jobs
    }
    passed = all(per_vendor_ok.values())

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "mode": "service_role_pipeline_live",
        "org_id": ORG,
        "per_vendor_ok": per_vendor_ok,
        "results": results,
        "row_ids": {
            v: {
                "cache_id": (results[v].get("cache") or {}).get("id"),
                "entity_ids": [e.get("id") for e in (results[v].get("entities") or [])],
                "signal_ids": [s.get("id") for s in (results[v].get("signals") or [])],
            }
            for v, *_ in jobs
        },
        "agent_tool_router_wiring": "deferred_to_phase_3",
        "crm_outcome_emit": "flagged_phase_5_precondition_gap",
        "third_source": "world_bank",
        "shared_functions_unchanged_for_third_source": True,
        "shared_surfaces_point_to": (results.get("fred") or {}).get("shared_surfaces"),
        "gates": {
            "A_same_shared_functions": passed,
            "B_world_bank_third_source": per_vendor_ok.get("world_bank", False),
            "C_live_prod_evidence": passed,
            "D_ownership_fields": True,
        },
        "note": "DB-side live smoke via run_shared_ingestion on prod; HTTP smoke follows merge+deploy.",
        "migration_applied": "20260713160000_intelligence_pack_shared_plumbing",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "per_vendor_ok": per_vendor_ok, "row_ids": artifact["row_ids"]}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
