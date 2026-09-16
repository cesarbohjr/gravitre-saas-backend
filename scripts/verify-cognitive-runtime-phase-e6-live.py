#!/usr/bin/env python3
"""E6 live GA4 verification on the isolated smoke org.

Ops probe, not architecture:
  - live auth gate (list_executable_integrations / find_integration_availability)
  - token refresh attempt (no Google consent UI)
  - chat cases: chitchat, GA4 traffic, website doing

Writes docs/delivery/cognitive-runtime-phase-e6-live.json
Exit 0 = PASS (GA4 cases ran and passed)
Exit 2 = EXTERNAL_BLOCKED (OAuth cannot be repaired without human Google login)
Exit 1 = FAIL
Exit 3 = NOT RUN (prod SHA mismatch)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("PYTHONPATH", str(BACKEND))

PHASE_D = ROOT / "scripts" / "verify-cognitive-runtime-phase-d-live.py"
spec = importlib.util.spec_from_file_location("phase_d_live", PHASE_D)
assert spec and spec.loader
phase_d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase_d)

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "cognitive-runtime-phase-e6-live.json"
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "dec0e169").strip()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ga4_row(sb: Any, org_id: str) -> dict[str, Any] | None:
    rows = (
        sb.table("connectors")
        .select("id,type,status,config,updated_at")
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .execute()
    ).data or []
    for row in rows:
        typ = str(row.get("type") or "").strip().lower()
        if typ in {"google_analytics", "ga4", "analytics"}:
            cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
            return {
                "id": row.get("id"),
                "type": typ,
                "status": row.get("status"),
                "updated_at": row.get("updated_at"),
                "has_property_id": bool(cfg.get("property_id") or cfg.get("propertyId")),
                "oauth_error": cfg.get("oauth_error"),
            }
    return None


async def _prod_connectors(client: httpx.AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    """Availability as evaluated on Railway (prod Google OAuth credentials)."""
    json_headers = {k: v for k, v in headers.items() if k != "Accept"}
    r = await client.get(
        f"{BASE}/api/connectors",
        params={"live": "true"},
        headers=json_headers,
        timeout=60,
    )
    r.raise_for_status()
    payload = r.json()
    rows = payload.get("connectors") if isinstance(payload, dict) else payload
    return list(rows or [])


def _ga4_from_prod(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        vendor = str(row.get("vendor") or row.get("type") or "").strip().lower()
        if vendor in {"google_analytics", "ga4", "analytics"}:
            avail = row.get("availability") if isinstance(row.get("availability"), dict) else {}
            return {
                "id": row.get("id"),
                "type": vendor,
                "status": row.get("status"),
                "authStatus": row.get("authStatus"),
                "displayStatus": row.get("displayStatus"),
                "executable": bool(avail.get("executable")),
                "tokenValid": avail.get("tokenValid"),
                "authenticated": avail.get("authenticated"),
                "configured": avail.get("configured"),
                "blockingReason": avail.get("blockingReason"),
                "recoveryAction": avail.get("recoveryAction"),
            }
    return None


async def main() -> int:
    env = phase_d.load_env()
    from supabase import create_client
    import jwt
    import time

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = phase_d.resolve_isolated_conversation_actor(env, sb)
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        **phase_d.smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    report: dict[str, Any] = {
        "probe": "cognitive_runtime_phase_e6_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA,
        "cases": [],
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["git_sha"] = sha
        report["health_timestamp"] = health.get("timestamp")
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"], "git_sha": sha}, indent=2))
            return 3

        prod_connectors = await _prod_connectors(client, headers)
        report["prod_connectors"] = [
            {
                "id": c.get("id"),
                "vendor": c.get("vendor") or c.get("type"),
                "status": c.get("status"),
                "authStatus": c.get("authStatus"),
                "executable": (c.get("availability") or {}).get("executable")
                if isinstance(c.get("availability"), dict)
                else None,
                "blockingReason": (c.get("availability") or {}).get("blockingReason")
                if isinstance(c.get("availability"), dict)
                else None,
            }
            for c in prod_connectors
        ]
        ga4_prod = _ga4_from_prod(prod_connectors)
        report["ga4_prod"] = ga4_prod
        report["ga4_row_local_db"] = _ga4_row(sb, org_id)
        has_ga4_executable = bool(ga4_prod and ga4_prod.get("executable"))
        report["ga4_executable"] = has_ga4_executable
        report["oauth_gate"] = "prod GET /api/connectors?live=true"

        for case in phase_d.CASES:
            needs_ga4 = bool(case.get("expect_analytics_short_circuit"))
            if needs_ga4 and not has_ga4_executable:
                reason = "google_analytics not executable on prod live availability"
                if ga4_prod:
                    reason = (
                        f"{reason}; executable={ga4_prod.get('executable')} "
                        f"authStatus={ga4_prod.get('authStatus')} "
                        f"blockingReason={ga4_prod.get('blockingReason')} "
                        f"recoveryAction={ga4_prod.get('recoveryAction')}"
                    )
                else:
                    reason = f"{reason}; no google_analytics connector in prod list"
                report["cases"].append(
                    {
                        "id": case["id"],
                        "message": case["message"],
                        "passed": False,
                        "verdict": "EXTERNAL_BLOCKED",
                        "reason": reason,
                    }
                )
                continue
            try:
                turn = await phase_d.run_turn(
                    client,
                    headers,
                    org_id,
                    str(case["message"]),
                    timeout=300.0 if needs_ga4 else phase_d.CHAT_TIMEOUT,
                )
                scored = phase_d.score_case(case, turn)
                report["cases"].append(
                    {
                        "id": case["id"],
                        "message": case["message"],
                        **scored,
                        "conversation_id": turn.get("conversation_id"),
                        "http_status": turn.get("http_status"),
                        "routing": turn.get("routing"),
                        "turn_id": (turn.get("cognitive_turn_trace") or {}).get("turn_id")
                        if isinstance(turn.get("cognitive_turn_trace"), dict)
                        else None,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                report["cases"].append(
                    {
                        "id": case["id"],
                        "message": case["message"],
                        "passed": False,
                        "verdict": "FAIL",
                        "error": f"{exc.__class__.__name__}: {exc}",
                    }
                )

    blocked = [c for c in report["cases"] if c.get("verdict") == "EXTERNAL_BLOCKED"]
    failed = [c for c in report["cases"] if c.get("verdict") == "FAIL"]
    report["finished_at"] = utcnow()
    if failed:
        report["verdict"] = "FAIL"
        code = 1
    elif blocked:
        report["verdict"] = "EXTERNAL_BLOCKED"
        code = 2
    elif all(c.get("passed") for c in report["cases"]) and report["cases"]:
        report["verdict"] = "PASS"
        code = 0
    else:
        report["verdict"] = "FAIL"
        code = 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "git_sha": report.get("git_sha"),
                "ga4_executable": report.get("ga4_executable"),
                "ga4_prod": report.get("ga4_prod"),
                "cases": [
                    {"id": c.get("id"), "verdict": c.get("verdict"), "reason": c.get("reason")}
                    for c in report["cases"]
                ],
            },
            indent=2,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(__import__("asyncio").run(main()))
