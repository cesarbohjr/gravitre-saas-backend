#!/usr/bin/env python3
"""Live verify BusinessOutcome: GET DTO + export content identity + tip git_sha.

Usage:
  python scripts/verify-business-outcome-live.py [--run-id UUID] [--expect-sha PREFIX]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import jwt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

from gravitree_test_client import (  # noqa: E402
    load_env,
    require_isolated_org,
    resolve_test_actor,
    smoke_http_headers,
)

BASE = "https://api.gravitre.app"
ENV_NAME = "production"
OUT = ROOT / "docs" / "delivery" / "business-outcome-live.json"


def mint(env: dict, user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 7200,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def req(method: str, path: str, token: str, org_id: str, timeout: int = 120):
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    request = urllib.request.Request(f"{BASE}{path}", method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-Org-Id", org_id)
    request.add_header("X-Environment", ENV_NAME)
    for k, v in smoke_http_headers().items():
        request.add_header(k, v)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def _business_core(dto: dict) -> dict:
    sections = dict(dto.get("sections") or {})
    return {
        "id": dto.get("id"),
        "kind": dto.get("kind"),
        "title": dto.get("title"),
        "status": dto.get("status"),
        "lifecycleState": dto.get("lifecycleState"),
        "lifecycleStatesReached": dto.get("lifecycleStatesReached"),
        "sections": {
            k: sections[k]
            for k in (
                "summary",
                "explanation",
                "verification",
                "evidence",
                "timeline",
                "recommendations",
                "approval",
                "diff",
                "undo",
            )
            if k in sections
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="")
    parser.add_argument("--expect-sha", default="")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    env = load_env()
    org_id, user_id, email = resolve_test_actor(env)
    org_id = require_isolated_org(org_id)
    token = mint(env, user_id, email)

    st, health_raw = req("GET", "/health", token, org_id)
    health = json.loads(health_raw) if health_raw.startswith("{") else {}
    tip = str(health.get("git_sha") or health.get("gitSha") or "")
    if args.expect_sha and not tip.startswith(args.expect_sha):
        report = {
            "verdict": "NOT RUN",
            "reason": f"tip {tip} does not match expect-sha {args.expect_sha}",
            "tipGitSha": tip,
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }
        Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    run_id = args.run_id.strip()
    if not run_id:
        st, listing_raw = req("GET", "/api/business-outcomes?limit=5", token, org_id)
        listing = json.loads(listing_raw) if listing_raw.startswith("{") else {}
        items = listing.get("businessOutcomes") or []
        if not items:
            st, runs_raw = req("GET", "/api/runs?limit=5", token, org_id)
            runs = json.loads(runs_raw) if runs_raw.startswith("{") else {}
            rows = runs.get("runs") or runs.get("items") or []
            if not rows:
                report = {
                    "verdict": "FAIL",
                    "reason": "no business outcomes or runs in isolated org",
                    "tipGitSha": tip,
                    "listStatus": st,
                    "listBody": listing_raw[:500],
                }
                Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(report, indent=2))
                return 1
            run_id = str(rows[0].get("id"))
        else:
            run_id = str(items[0].get("id") or items[0].get("runId"))

    st, detail_raw = req("GET", f"/api/business-outcomes/{run_id}", token, org_id)
    detail = json.loads(detail_raw) if detail_raw.startswith("{") else {}
    dto = detail.get("businessOutcome") or {}

    st_ex, export_raw = req(
        "GET", f"/api/business-outcomes/{run_id}/export?format=json", token, org_id
    )
    export = json.loads(export_raw) if export_raw.startswith("{") else {}
    export_dto = export.get("businessOutcome") or {}

    identical = bool(dto) and _business_core(dto) == _business_core(export_dto)
    from app.services.business_outcome.catalog_reversal import undo_availability

    irreversible = undo_availability("gmail.messages.send")
    reversible = undo_availability("hubspot.contacts.create")

    route_ok = st == 200 and dto.get("projection") == "business_outcome"
    report = {
        "verdict": "PASS" if route_ok and identical else "FAIL",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "tipGitSha": tip,
        "outcomeId": run_id,
        "getStatus": st,
        "exportStatus": st_ex,
        "projection": dto.get("projection"),
        "pipelineStagesCompleted": dto.get("pipelineStagesCompleted"),
        "lifecycleState": dto.get("lifecycleState"),
        "lifecycleStatesReached": dto.get("lifecycleStatesReached"),
        "getExportBusinessContentIdentical": identical,
        "unshippedLifecycleStates": ["reviewed", "edited", "referenced", "archived"],
        "catalogUndo": {
            "gmail.messages.send": irreversible,
            "hubspot.contacts.create": reversible,
        },
        "sectionsPresent": sorted((dto.get("sections") or {}).keys()),
        "omittedFabricated": {
            "impact": "impact" not in (dto.get("sections") or {}),
            "related": "relatedOutcomes" not in (dto.get("sections") or {}),
            "history": "history" not in (dto.get("sections") or {}),
        },
        "detailSnippet": {
            "title": dto.get("title"),
            "kind": dto.get("kind"),
            "status": dto.get("status"),
        },
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
