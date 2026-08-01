#!/usr/bin/env python3
"""Upgrade org workflows named 'MSP NVD CVE Lookup' to MSP Prospecting & List Builder.

Usage (service role):
  python scripts/upgrade-msp-nvd-workflow-to-prospecting.py --org-id <uuid>
  python scripts/upgrade-msp-nvd-workflow-to-prospecting.py --all-orgs
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.config import get_settings  # noqa: E402
from app.core.db import get_supabase_client  # noqa: E402
from app.marketplace.intelligence_packs.msp_install import (  # noqa: E402
    LEGACY_WORKFLOW_NAMES,
    _upsert_workflow,
)
from app.marketplace.workflows.msp_prospecting_list_workflow import (  # noqa: E402
    WORKFLOW_DESCRIPTION,
    WORKFLOW_NAME,
    build_msp_prospecting_list_workflow_steps,
)


def _upgrade_org(client, org_id: str, *, actor_id: str, environment: str) -> list[str]:
    steps = build_msp_prospecting_list_workflow_steps()
    rows = (
        client.table("workflows")
        .select("id, name")
        .eq("org_id", org_id)
        .eq("environment", environment)
        .in_("name", list(LEGACY_WORKFLOW_NAMES))
        .execute()
        .data
        or []
    )
    upgraded: list[str] = []
    for row in rows:
        wid = str(row.get("id") or "")
        if not wid:
            continue
        _upsert_workflow(
            client,
            org_id=org_id,
            workflow_id=wid,
            asset_id="upgrade-script",
            pack_id="msp-intelligence-pack",
            name=WORKFLOW_NAME,
            description=WORKFLOW_DESCRIPTION,
            steps=steps,
            environment_name=environment,
            actor_id=actor_id,
        )
        upgraded.append(wid)
    return upgraded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id")
    parser.add_argument("--all-orgs", action="store_true")
    parser.add_argument("--environment", default="production")
    parser.add_argument("--actor-id", default="upgrade-script")
    args = parser.parse_args()
    if not args.org_id and not args.all_orgs:
        parser.error("pass --org-id or --all-orgs")

    settings = get_settings()
    client = get_supabase_client(settings)
    org_ids: list[str]
    if args.all_orgs:
        rows = (
            client.table("workflows")
            .select("org_id")
            .eq("environment", args.environment)
            .in_("name", list(LEGACY_WORKFLOW_NAMES))
            .execute()
            .data
            or []
        )
        org_ids = sorted({str(r["org_id"]) for r in rows if r.get("org_id")})
    else:
        org_ids = [args.org_id]

    total = 0
    for org_id in org_ids:
        ids = _upgrade_org(
            client, org_id, actor_id=args.actor_id, environment=args.environment
        )
        print(f"org={org_id} upgraded={len(ids)} ids={ids}")
        total += len(ids)
    print(f"total_upgraded={total}")
    return 0 if total >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
