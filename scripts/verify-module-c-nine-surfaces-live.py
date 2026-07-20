#!/usr/bin/env python3
"""Pull live prod JSON for each Module C Round-2 surface and quote labeling fields."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ENV_NAME = "production"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip('"')
                if value:
                    merged[key.strip()] = value
    return merged


def _mint(env: dict[str, str], user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def _admin(env: dict[str, str]) -> tuple[str, str, str]:
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id = (os.environ.get("SMOKE_ORG_ID") or env.get("SMOKE_ORG_ID") or "").strip()
    if not org_id:
        rows = (
            client.table("organization_members")
            .select("org_id,user_id,role")
            .eq("role", "owner")
            .limit(1)
            .execute()
            .data
            or []
        )
        org_id, user_id = str(rows[0]["org_id"]), str(rows[0]["user_id"])
    else:
        rows = (
            client.table("organization_members")
            .select("user_id,role")
            .eq("org_id", org_id)
            .in_("role", ["owner", "admin"])
            .limit(1)
            .execute()
            .data
            or []
        )
        user_id = str(rows[0]["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = getattr(getattr(users, "user", None), "email", None) or f"{user_id}@smoke.local"
    return org_id, user_id, str(email)


def _req(method: str, path: str, token: str, org_id: str, body: dict | None = None) -> tuple[int, Any]:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    req.add_header("X-Gravitree-Smoke-Run", "1")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw.strip() else {"detail": raw}
        except json.JSONDecodeError:
            parsed = {"detail": raw[:300]}
        return exc.code, parsed


def _quote_conf(payload: Any, *, prefix: str = "") -> dict[str, Any]:
    if isinstance(payload, list):
        first = next((x for x in payload if isinstance(x, dict)), None)
        return _quote_conf(first or {}, prefix=prefix)
    if not isinstance(payload, dict):
        return {"raw_type": type(payload).__name__}
    keys = [
        "confidence",
        "confidenceIsEstimate",
        "confidence_is_estimate",
        "confidenceSource",
        "confidence_source",
        "runtime_status",
        "live_inference_path",
        "artifact_loaded",
        "note",
    ]
    out = {k: payload.get(k) for k in keys if k in payload}
    # nested signals / suggestions / entities
    for nest in ("signals", "suggestions", "entities", "recommended_actions", "orgTrainingStatus"):
        if nest in payload and payload[nest]:
            child = payload[nest]
            if isinstance(child, dict):
                # orgTrainingStatus is map
                first_key = next(iter(child), None)
                if first_key:
                    out[f"{nest}.{first_key}"] = _quote_conf(child[first_key])
            elif isinstance(child, list) and child:
                out[f"{nest}[0]"] = _quote_conf(child[0])
    return out


def main() -> int:
    env = _load_env()
    with urllib.request.urlopen(f"{API_BASE}/health", timeout=30) as resp:
        health = json.loads(resp.read().decode())
    org_id, user_id, email = _admin(env)
    token = _mint(env, user_id, email)

    report: dict[str, Any] = {
        "target": API_BASE,
        "git_sha": health.get("git_sha"),
        "health_ts": health.get("timestamp"),
        "org_id": org_id,
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "surfaces": {},
    }

    # 1 advisor-brief (feeds advisor-brief-panel + meson-page-panel)
    code, body = _req("GET", "/api/assistant/advisor-brief", token, org_id)
    report["surfaces"]["1_advisor_brief"] = {
        "http": code,
        "quote": _quote_conf(body),
        "action0": _quote_conf((body.get("recommended_actions") or [None])[0] or {}),
    }

    # 2 MesonInterpretResult
    code, body = _req(
        "POST",
        "/api/meson/interpret",
        token,
        org_id,
        {
            "intent": "Monitor overdue invoices and notify finance weekly",
            "department": "finance",
            "systems": ["quickbooks"],
            "outputTypes": ["workflow"],
        },
    )
    report["surfaces"]["2_meson_interpret"] = {"http": code, "quote": _quote_conf(body) if code < 400 else body}

    # 3 trust-summary → RecommendationExplanation / ConfidenceBadge isEstimate wiring
    code, body = _req("GET", "/api/admin/intelligence/trust-summary?periodDays=7", token, org_id)
    if code >= 400:
        code, body = _req("GET", "/api/intelligence/trust-summary?periodDays=7", token, org_id)
    report["surfaces"]["3_trust_summary_for_confidence_badge"] = {
        "http": code,
        "quote": {
            "avg_confidence": body.get("avg_confidence") if isinstance(body, dict) else None,
            "confidence_is_estimate": body.get("confidence_is_estimate") if isinstance(body, dict) else None,
            "confidenceIsEstimate": body.get("confidenceIsEstimate") if isinstance(body, dict) else None,
            "confidence_source": body.get("confidence_source") if isinstance(body, dict) else None,
            "keys": sorted(body.keys())[:40] if isinstance(body, dict) else [],
        },
    }

    # 4 intelligence_router forecast
    code, body = _req(
        "POST",
        "/api/intelligence/forecast",
        token,
        org_id,
        {"metric": "revenue", "horizon_days": 30},
    )
    report["surfaces"]["4_intelligence_forecast"] = {"http": code, "quote": _quote_conf(body)}

    # 5 business_signals
    code, body = _req("GET", "/api/assistant/business-signals", token, org_id)
    signals = body.get("signals") if isinstance(body, dict) else body
    if not isinstance(signals, list):
        signals = []
    report["surfaces"]["5_business_signals"] = {
        "http": code,
        "count": len(signals),
        "quote": _quote_conf(signals[0] if signals else body),
    }

    # 6 entity_relationship_builder → KG score_relationship (consumes stored edge heuristics)
    code, body = _req(
        "POST",
        "/api/intelligence/explain",
        token,
        org_id,
        {"entity_type": "department", "entity_id": "sales"},
    )
    if code >= 400:
        # try graph score endpoints
        for path, method, payload in (
            ("/api/intelligence/graph/score", "POST", {"source_entity_id": "a", "target_entity_id": "b"}),
            ("/api/admin/intelligence/knowledge-graph/score", "POST", {"source": "a", "target": "b"}),
        ):
            code2, body2 = _req(method, path, token, org_id, payload)
            if code2 < 400:
                code, body = code2, body2
                break
    report["surfaces"]["6_kg_or_entity_relationship"] = {"http": code, "quote": _quote_conf(body) if code < 400 else body}

    # 7 contextual_understanding — exposed via intelligence ask / dialogue classify paths
    code, body = _req(
        "POST",
        "/api/intelligence/ask",
        token,
        org_id,
        {"question": 'Show the "Acme" workflow and agent connector status', "mode": "standard"},
    )
    report["surfaces"]["7_intelligence_ask_contextual"] = {
        "http": code,
        "quote": _quote_conf(body) if isinstance(body, dict) else {"raw": str(body)[:200]},
        "enrichment_entities": _quote_conf(
            (((body.get("enrichments") or {}).get("contextual") or {}).get("entities") or [None])[0] or {}
        )
        if isinstance(body, dict)
        else {},
        "keys": sorted(body.keys())[:50] if isinstance(body, dict) else [],
    }

    # 8 optimization_service
    code, body = _req(
        "POST",
        "/api/optimization/analyze",
        token,
        org_id,
        {"workflow_id": "00000000-0000-0000-0000-000000000001", "days": 30},
    )
    report["surfaces"]["8_optimization_analyze"] = {
        "http": code,
        "quote": _quote_conf(body[0] if isinstance(body, list) and body else body),
        "count": len(body) if isinstance(body, list) else None,
    }

    # models runtime (Round 1 prod PASS bar)
    code, body = _req("GET", "/api/admin/ml/models/intent_classifier/status", token, org_id)
    report["surfaces"]["models_runtime_status"] = {"http": code, "quote": _quote_conf(body) if code < 400 else body}
    code, dash = _req("GET", "/api/admin/ml/models", token, org_id)
    org_status = dash.get("orgTrainingStatus") if isinstance(dash, dict) else {}
    sample_name = next(iter(org_status or {}), None)
    report["surfaces"]["models_dashboard_sample"] = {
        "http": code,
        "sample_model": sample_name,
        "quote": _quote_conf(org_status.get(sample_name) if sample_name else {}),
    }

    out = REPO / "docs" / "delivery" / "module-c-nine-surfaces-live.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
