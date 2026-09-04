#!/usr/bin/env python3
"""Live verification for department signal-source audit and weighted scoring."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "signal-scoring-live.json"
DEPARTMENTS = ("sales", "marketing", "finance", "hr", "msp")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def _auth_headers(env: dict[str, str], org_id: str, user_id: str, email: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    return {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
    }


def _extract_source_statuses(audit_payload: dict[str, Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in list(audit_payload.get("departments") or []):
        dept = str(row.get("department") or "")
        counts = row.get("counts") if isinstance(row.get("counts"), dict) else {}
        out[dept] = {
            "live_connector": int(counts.get("live_connector") or 0),
            "knowledge_fabric_only": int(counts.get("knowledge_fabric_only") or 0),
            "missing": int(counts.get("missing") or 0),
        }
    return out


def _priority_summary(payload: dict[str, Any]) -> dict[str, Any]:
    priorities = list(payload.get("priorities") or [])
    explainable = 0
    top: dict[str, Any] | None = None
    for row in priorities:
        if list(row.get("signalContributions") or []) and list(row.get("explanations") or []):
            explainable += 1
    if priorities:
        top = priorities[0]
    return {
        "count": len(priorities),
        "explainableCount": explainable,
        "top": {
            "workObjectId": top.get("workObjectId"),
            "title": top.get("title"),
            "priorityScore": top.get("priorityScore"),
            "priorityBand": top.get("priorityBand"),
            "explanations": list(top.get("explanations") or [])[:3],
        }
        if top
        else None,
        "gaps": list(payload.get("gaps") or [])[:8],
    }


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    headers = _auth_headers(env, org_id, user_id, email)

    report: dict[str, Any] = {
        "probe": "verify_signal_scoring_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "departments": {},
        "global_gaps": [],
    }

    with httpx.Client(timeout=120.0) as http:
        health = http.get(f"{BASE}/health")
        report["health"] = health.json() if health.headers.get("content-type", "").startswith("application/json") else {}

        audit_r = http.get(
            f"{BASE}/api/assistant/business-signals/source-audit",
            headers=headers,
        )
        report["source_audit_http"] = audit_r.status_code
        audit_payload: dict[str, Any] = audit_r.json() if audit_r.status_code == 200 else {}
        report["source_audit"] = _extract_source_statuses(audit_payload)

        for dept in DEPARTMENTS:
            resp = http.get(
                f"{BASE}/api/assistant/business-signals/priorities",
                headers=headers,
                params={"department": dept, "limit": 3},
            )
            body: dict[str, Any] = resp.json() if resp.status_code == 200 else {}
            summary = _priority_summary(body)
            report["departments"][dept] = {
                "http": resp.status_code,
                **summary,
            }
            if summary["count"] == 0:
                report["global_gaps"].append(f"{dept}: no representative WorkObjects were available to score.")
            if summary["count"] > 0 and summary["explainableCount"] == 0:
                report["global_gaps"].append(f"{dept}: scored rows exist but missing contribution explanations.")

    source_ok = report.get("source_audit_http") == 200
    dept_http_ok = all(int((report["departments"][d] or {}).get("http") or 0) == 200 for d in DEPARTMENTS)
    has_all_representative = all(int((report["departments"][d] or {}).get("count") or 0) > 0 for d in DEPARTMENTS)
    all_explainable = all(
        int((report["departments"][d] or {}).get("count") or 0) == 0
        or int((report["departments"][d] or {}).get("explainableCount") or 0) > 0
        for d in DEPARTMENTS
    )
    if source_ok and dept_http_ok and has_all_representative and all_explainable:
        verdict = "PASS"
    elif source_ok and dept_http_ok and all_explainable:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    report["verdict"] = verdict
    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "report": str(OUT), "git_sha": (report.get("health") or {}).get("git_sha")}, indent=2))
    return 0 if verdict in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
