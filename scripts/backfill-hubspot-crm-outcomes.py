#!/usr/bin/env python3
"""Backfill HubSpot closed won/lost deals into crm_recommendation_outcomes (Phase 5.0).

Uses pipeline metadata (isClosed) + explicit dealstage values. Soft-dedupes.
When the smoke org has only open \"Gravitre Smoke Deal*\" rows, transitions a few
to closedwon/closedlost so real CRM volume can accumulate (authorized smoke data).

Writes docs/delivery/phase5-hubspot-crm-outcomes-backfill-live.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
OUT = REPO / "docs" / "delivery" / "phase5-hubspot-crm-outcomes-backfill-live.json"
LIMIT_PER_STAGE = 50
SMOKE_DEAL_PREFIX = "Gravitre Smoke Deal"


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
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and val:
                    merged[key] = val
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _closed_stage_ids(token: str) -> tuple[set[str], set[str]]:
    from app.connectors.hubspot import list_deal_pipelines
    from app.services.hubspot_trigger_service import (
        CLOSED_LOST_DEALSTAGES,
        CLOSED_WON_DEALSTAGES,
    )

    won: set[str] = set(CLOSED_WON_DEALSTAGES)
    lost: set[str] = set(CLOSED_LOST_DEALSTAGES)
    pipes = list_deal_pipelines(token)
    for pipe in pipes.get("results") or []:
        for stage in pipe.get("stages") or []:
            sid = str(stage.get("id") or "").strip().lower()
            meta = stage.get("metadata") or {}
            if str(meta.get("isClosed") or "").lower() != "true":
                continue
            prob = float(meta.get("probability") or 0)
            if prob >= 1.0:
                won.add(sid)
            else:
                lost.add(sid)
    return won, lost


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.connectors.hubspot import list_deals, search_deals, update_deal_stage
    from app.connectors.hubspot_oauth import ensure_hubspot_access_token
    from app.services.crm_outcome_capture_service import (
        count_crm_outcomes,
        ingest_crm_recommendation_outcome,
    )

    settings = get_settings()
    sb = create_client_safe(settings)

    connectors = (
        sb.table("connectors")
        .select("id,type,status,org_id")
        .eq("org_id", ORG)
        .eq("type", "hubspot")
        .in_("status", ["active", "healthy", "connected", "ready"])
        .limit(5)
        .execute()
    ).data or []
    if not connectors:
        return _fail({"error": "no_usable_hubspot_connector"})

    connectors.sort(key=lambda r: 0 if str(r.get("status")) == "healthy" else 1)
    connector = connectors[0]
    connector_id = str(connector["id"])
    token, err = ensure_hubspot_access_token(sb, ORG, connector_id, settings)
    if err or not token:
        return _fail({"connector_id": connector_id, "error": err or "missing_token"})

    won_stages, lost_stages = _closed_stage_ids(token)
    seed_actions: list[dict] = []

    # Seed smoke deals into closed stages when none are closed yet.
    open_smoke = []
    listed = list_deals(token, limit=50)
    for deal in listed.get("results") or []:
        props = deal.get("properties") or {}
        name = str(props.get("dealname") or "")
        stage = str(props.get("dealstage") or "").strip().lower()
        if not name.startswith(SMOKE_DEAL_PREFIX):
            continue
        if stage in won_stages or stage in lost_stages:
            continue
        open_smoke.append(str(deal.get("id")))

    if open_smoke:
        # Prefer canonical ids when present.
        won_id = "closedwon" if "closedwon" in won_stages else next(iter(won_stages))
        lost_id = "closedlost" if "closedlost" in lost_stages else next(iter(lost_stages))
        for i, deal_id in enumerate(open_smoke):
            target = won_id if i % 2 == 0 else lost_id
            update_deal_stage(token, deal_id, target)
            seed_actions.append({"deal_id": deal_id, "dealstage": target})

    before = count_crm_outcomes(sb, ORG)
    stored = 0
    deduped = 0
    scanned = 0
    samples: list[dict] = []

    stage_batches = [
        ("won", sorted(won_stages)),
        ("lost", sorted(lost_stages)),
    ]
    for outcome_type, stages in stage_batches:
        for stage in stages:
            try:
                result = search_deals(
                    token,
                    filter_groups=[
                        {
                            "filters": [
                                {
                                    "propertyName": "dealstage",
                                    "operator": "EQ",
                                    "value": stage,
                                }
                            ]
                        }
                    ],
                    properties=["dealname", "dealstage", "amount", "closedate"],
                    limit=LIMIT_PER_STAGE,
                )
            except Exception as exc:  # noqa: BLE001
                samples.append({"stage": stage, "error": exc.__class__.__name__})
                continue
            for deal in result.get("results") or []:
                scanned += 1
                deal_id = str(deal.get("id") or "")
                props = deal.get("properties") or {}
                emit = ingest_crm_recommendation_outcome(
                    sb,
                    org_id=ORG,
                    outcome_type=outcome_type,
                    connector_type="hubspot",
                    external_record_id=deal_id,
                    metadata={
                        "source": "hubspot_backfill",
                        "dealstage": props.get("dealstage") or stage,
                        "dealname": props.get("dealname"),
                        "amount": props.get("amount"),
                        "closedate": props.get("closedate"),
                    },
                    occurred_at=props.get("closedate") or None,
                )
                if emit.get("stored"):
                    stored += 1
                    if len(samples) < 10:
                        samples.append(
                            {
                                "deal_id": deal_id,
                                "outcome": outcome_type,
                                "id": emit.get("id"),
                                "stage": stage,
                            }
                        )
                elif emit.get("deduped"):
                    deduped += 1

    after = count_crm_outcomes(sb, ORG)
    passed = stored > 0 or (scanned > 0 and deduped > 0)
    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "org_id": ORG,
        "connector_id": connector_id,
        "count_before": before,
        "count_after": after,
        "scanned": scanned,
        "stored": stored,
        "deduped": deduped,
        "seed_actions": seed_actions,
        "won_stages": sorted(won_stages),
        "lost_stages": sorted(lost_stages),
        "samples": samples,
        "phase_5": "IN_PROGRESS",
        "note": (
            "HubSpot closed deal backfill into crm_recommendation_outcomes "
            "(pipeline isClosed + explicit dealstage). Smoke deals seeded to closed "
            "stages when none were closed. Mirrors to intelligence_outcome_events on insert."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: artifact[k]
                for k in (
                    "pass",
                    "count_before",
                    "count_after",
                    "stored",
                    "deduped",
                    "scanned",
                    "seed_actions",
                )
            },
            indent=2,
        )
    )
    return 0 if passed else 1


def create_client_safe(settings):
    from supabase import create_client

    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _fail(extra: dict) -> int:
    artifact = {"pass": False, "ran_at": utcnow(), "org_id": ORG, **extra}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
