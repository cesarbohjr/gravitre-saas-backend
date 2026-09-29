#!/usr/bin/env python3
"""Authenticated, non-destructive live proof for Plays + external dataset connectors.

This script performs GET requests only. It does not bind workflows, execute
workflows, create/delete dataset references, download provider content, or
materialize datasets.

Required:
  PLATFORM_LIVE_BEARER_TOKEN
  PLATFORM_LIVE_ORG_ID

Optional:
  BACKEND_URL                defaults to production Railway backend
  PLATFORM_LIVE_ENVIRONMENT  defaults to production
  DATASET_LIVE_QUERY         defaults to "customer support"

Output:
  docs/delivery/plays-datasets-live-proof.json
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "delivery" / "plays-datasets-live-proof.json"
BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")


def _required(name: str) -> str:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


def _get(client: httpx.Client, path: str) -> dict:
    response = client.get(path)
    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text[:500]}
    return {
        "path": path,
        "status_code": response.status_code,
        "payload": payload,
    }


def main() -> int:
    token = _required("PLATFORM_LIVE_BEARER_TOKEN")
    org_id = _required("PLATFORM_LIVE_ORG_ID")
    environment = os.environ.get("PLATFORM_LIVE_ENVIRONMENT", "production")
    query = os.environ.get("DATASET_LIVE_QUERY", "customer support")

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "X-Environment": environment,
    }
    paths = [
        "/health",
        "/api/plays",
        "/api/plays/revenue-recovery/readiness",
        "/api/plays/revenue-recovery/observe",
        "/api/plays/customer-rescue/readiness",
        "/api/plays/customer-rescue/observe",
        "/api/plays/marketing-performance/readiness",
        "/api/plays/marketing-performance/observe",
        "/api/training/external-datasets/providers",
        f"/api/training/external-datasets/search?provider=huggingface&q={quote_plus(query)}&limit=5",
    ]

    with httpx.Client(base_url=BASE, headers=headers, timeout=90.0) as client:
        probes = [_get(client, path) for path in paths]

    failures: list[str] = []

    for probe in probes:
        if probe["status_code"] != 200:
            failures.append(f'{probe["path"]}:HTTP_{probe["status_code"]}')

    by_path = {p["path"]: p for p in probes}

    plays = by_path.get("/api/plays", {}).get("payload") or {}
    if isinstance(plays, dict):
        if plays.get("executionAuthority") != "canonical_workflow_runtime":
            failures.append("plays:wrong_execution_authority")
        for item in plays.get("plays") or []:
            play = item.get("play") or {}
            readiness = item.get("readiness") or {}
            if play.get("executable") is not False:
                failures.append(f'plays:{play.get("key")}:executable_not_false')
            if readiness.get("act_within_policy_ready") is True:
                failures.append(f'plays:{play.get("key")}:policy_not_fail_closed')

    for probe in probes:
        if probe["path"].endswith("/observe") and probe["status_code"] == 200:
            payload = probe["payload"] if isinstance(probe["payload"], dict) else {}
            if payload.get("actionTaken") is not False:
                failures.append(f'{probe["path"]}:actionTaken_not_false')

    providers = by_path.get("/api/training/external-datasets/providers", {}).get("payload") or {}
    if isinstance(providers, dict):
        if providers.get("mutation") is not False:
            failures.append("datasets:providers_mutation_not_false")
        if providers.get("materialization") != "explicit_only":
            failures.append("datasets:materialization_not_explicit_only")
        provider_ids = {str(row.get("id") or "") for row in providers.get("providers") or []}
        if "huggingface" not in provider_ids:
            failures.append("datasets:huggingface_provider_missing")

    search_probe = next(
        (p for p in probes if p["path"].startswith("/api/training/external-datasets/search?")),
        None,
    )
    if search_probe and search_probe["status_code"] == 200:
        payload = search_probe["payload"] if isinstance(search_probe["payload"], dict) else {}
        if payload.get("mutation") is not False:
            failures.append("datasets:search_mutation_not_false")
        for row in payload.get("datasets") or []:
            if row.get("materialized") is True:
                failures.append(f"datasets:{row.get('dataset_id')}:unexpected_materialization")
            if row.get("private") or row.get("gated"):
                # Restricted rows may be visible as metadata only; proof requires
                # that no content/materialization payload is exposed.
                if row.get("content") is not None or row.get("rows") is not None:
                    failures.append(f"datasets:{row.get('dataset_id')}:restricted_content_exposed")

    health = by_path.get("/health", {}).get("payload") or {}
    report = {
        "at": datetime.now(timezone.utc).isoformat(),
        "backend_url": BASE,
        "org_id": org_id,
        "environment": environment,
        "git_sha": health.get("git_sha") if isinstance(health, dict) else None,
        "mutation": False,
        "dataset_query": query,
        "paths": probes,
        "failures": failures,
        "pass": not failures,
        "claim": (
            "PASS — Plays and external dataset connector live reads are non-destructive and policy-honest"
            if not failures
            else "FAIL — one or more Plays/dataset live gates failed"
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {k: report[k] for k in ("git_sha", "mutation", "failures", "pass", "claim")},
            indent=2,
        )
    )
    print("WROTE", OUT)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
