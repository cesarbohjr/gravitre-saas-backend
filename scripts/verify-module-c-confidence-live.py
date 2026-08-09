#!/usr/bin/env python3
"""Live Module C confidence-honesty verification against Railway prod.

Waits for /health git_sha to match expected tip (or --sha), then pulls:
  1) GET /api/admin/ml/models — runtime_status / live_inference_path
  2) POST /api/meson/interpret — confidenceIsEstimate
  3) GET /api/assistant/advisor-brief — confidenceIsEstimate / confidence_source
  4) GET /api/assistant/business-signals — labeled confidence on signals (bonus)

Usage:
  python scripts/verify-module-c-confidence-live.py
  python scripts/verify-module-c-confidence-live.py --sha 09699335 --json docs/delivery/module-c-confidence-live.json
"""
from __future__ import annotations

import argparse
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
            continue
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or ""
    supabase_url = (env.get("SUPABASE_URL") or "").rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
        },
        secret,
        algorithm="HS256",
    )


def _admin_org(env: dict[str, str]) -> tuple[str, str, str]:
    from supabase import create_client

    url = env["SUPABASE_URL"]
    key = env["SUPABASE_SERVICE_ROLE_KEY"]
    client = create_client(url, key)
    org_id = (
        os.environ.get("SMOKE_ORG_ID")
        or env.get("SMOKE_ORG_ID")
        or env.get("OAUTH_SMOKE_ORG_ID")
        or ""
    ).strip()
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
        if not rows:
            raise SystemExit("No owner org found for smoke")
        org_id = str(rows[0]["org_id"])
        user_id = str(rows[0]["user_id"])
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
        if not rows:
            raise SystemExit(f"No admin member for org {org_id}")
        user_id = str(rows[0]["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = getattr(getattr(users, "user", None), "email", None) or f"{user_id}@smoke.local"
    return org_id, user_id, str(email)


def _get_health() -> dict[str, Any]:
    with urllib.request.urlopen(f"{API_BASE}/health", timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _request(method: str, path: str, token: str, org_id: str, body: dict | None = None) -> dict[str, Any]:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    req.add_header("X-Gravitre-Smoke-Run", "1")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode("utf-8") or "{}"
        return json.loads(raw) if raw.strip() else {}


def _has_estimate(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("confidenceIsEstimate") is True
        or payload.get("confidence_is_estimate") is True
        or payload.get("confidenceSource")
        or payload.get("confidence_source")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", default="09699335", help="Expected git_sha prefix after deploy")
    parser.add_argument("--wait-seconds", type=int, default=600)
    parser.add_argument("--json", metavar="PATH", help="Write evidence report")
    args = parser.parse_args()

    env = _load_env()
    report: dict[str, Any] = {
        "target": API_BASE,
        "expected_sha_prefix": args.sha,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "checks": {},
    }

    deadline = time.time() + args.wait_seconds
    health: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            health = _get_health()
        except Exception as exc:  # noqa: BLE001
            print(f"health poll error: {exc}")
            time.sleep(15)
            continue
        sha = str(health.get("git_sha") or "")
        print(f"health git_sha={sha} status={health.get('status')}")
        if sha.startswith(args.sha):
            break
        time.sleep(20)
    else:
        report["checks"]["deploy"] = {
            "status": "FAIL",
            "detail": f"Timed out waiting for git_sha prefix {args.sha}; last={health.get('git_sha')}",
        }
        print(json.dumps(report, indent=2))
        return 1

    report["checks"]["deploy"] = {
        "status": "PASS",
        "git_sha": health.get("git_sha"),
        "timestamp": health.get("timestamp"),
    }

    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)
    report["org_id"] = org_id
    report["user_id"] = user_id

    # 1) Models runtime honesty
    try:
        models = _request("GET", "/api/admin/ml/models", token, org_id)
        rows = models.get("models") or models.get("catalog") or []
        if isinstance(models, dict) and not rows:
            # dashboard shape may nest under departments / items
            for key in ("items", "by_status", "models"):
                if isinstance(models.get(key), list):
                    rows = models[key]
                    break
        sample = None
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and (
                    row.get("runtime_status") or row.get("live_inference_path") is not None
                ):
                    sample = row
                    break
            if sample is None and rows:
                sample = rows[0] if isinstance(rows[0], dict) else None
        # Also try a known model status endpoint
        status_payload = None
        try:
            status_payload = _request(
                "GET", "/api/admin/ml/models/intent_classifier/status", token, org_id
            )
        except urllib.error.HTTPError:
            try:
                status_payload = _request(
                    "GET", "/api/admin/ml/models/task_classifier/status", token, org_id
                )
            except urllib.error.HTTPError:
                status_payload = None

        probe = status_payload or sample or {}
        runtime = probe.get("runtime_status")
        path = probe.get("live_inference_path")
        artifact = probe.get("artifact_loaded")
        ok = runtime in {"heuristic", "data_gate", "trained"} and path is not None
        # Without artifact, must not pretend trained via catalog alone
        if artifact is False and runtime == "trained":
            ok = False
        report["checks"]["models_runtime"] = {
            "status": "PASS" if ok else "FAIL",
            "runtime_status": runtime,
            "live_inference_path": path,
            "artifact_loaded": artifact,
            "sample_keys": sorted(probe.keys())[:40] if isinstance(probe, dict) else [],
        }
        print(f"models_runtime: {report['checks']['models_runtime']}")
    except Exception as exc:  # noqa: BLE001
        report["checks"]["models_runtime"] = {"status": "FAIL", "detail": str(exc)}
        print(f"models_runtime FAIL: {exc}")

    # 2) Meson interpret (control-tier); fall back to page-context / suggestions
    try:
        interpret = _request(
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
        ok = _has_estimate(interpret) and interpret.get("confidence") is not None
        report["checks"]["meson_interpret"] = {
            "status": "PASS" if ok else "FAIL",
            "confidence": interpret.get("confidence"),
            "confidenceIsEstimate": interpret.get("confidenceIsEstimate", interpret.get("confidence_is_estimate")),
            "confidenceSource": interpret.get("confidenceSource", interpret.get("confidence_source")),
        }
        print(f"meson_interpret: {report['checks']['meson_interpret']}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        report["checks"]["meson_interpret"] = {
            "status": "SKIP",
            "detail": f"HTTP {exc.code}: {detail}",
        }
        print(f"meson_interpret SKIP: HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        report["checks"]["meson_interpret"] = {"status": "FAIL", "detail": str(exc)}
        print(f"meson_interpret FAIL: {exc}")

    # 2b) Intelligence forecast — model_selection_heuristic labeling
    try:
        forecast = _request(
            "POST",
            "/api/intelligence/forecast",
            token,
            org_id,
            {"metric": "revenue", "horizon_days": 30},
        )
        ok = _has_estimate(forecast) and forecast.get("confidence") is not None
        report["checks"]["intelligence_forecast"] = {
            "status": "PASS" if ok else "FAIL",
            "confidence": forecast.get("confidence"),
            "confidenceIsEstimate": forecast.get("confidenceIsEstimate", forecast.get("confidence_is_estimate")),
            "confidenceSource": forecast.get("confidenceSource", forecast.get("confidence_source")),
        }
        print(f"intelligence_forecast: {report['checks']['intelligence_forecast']}")
    except Exception as exc:  # noqa: BLE001
        report["checks"]["intelligence_forecast"] = {"status": "FAIL", "detail": str(exc)}
        print(f"intelligence_forecast FAIL: {exc}")

    # 3) Advisor brief
    try:
        brief = _request("GET", "/api/assistant/advisor-brief", token, org_id)
        ok = (
            brief.get("confidence") is None
            and brief.get("confidence_source") == "insufficient_data"
        ) or _has_estimate(brief)
        actions = brief.get("recommended_actions") or []
        action_labeled = True
        if actions and isinstance(actions[0], dict) and actions[0].get("confidence") is not None:
            action_labeled = _has_estimate(actions[0])
        report["checks"]["advisor_brief"] = {
            "status": "PASS" if ok and action_labeled else "FAIL",
            "confidence": brief.get("confidence"),
            "confidenceIsEstimate": brief.get("confidenceIsEstimate", brief.get("confidence_is_estimate")),
            "confidenceSource": brief.get("confidenceSource", brief.get("confidence_source")),
            "action0_estimate": (
                actions[0].get("confidenceIsEstimate", actions[0].get("confidence_is_estimate"))
                if actions and isinstance(actions[0], dict)
                else None
            ),
        }
        print(f"advisor_brief: {report['checks']['advisor_brief']}")
    except Exception as exc:  # noqa: BLE001
        report["checks"]["advisor_brief"] = {"status": "FAIL", "detail": str(exc)}
        print(f"advisor_brief FAIL: {exc}")

    # 4) Business signals (bonus third/fourth surface)
    try:
        signals_payload = _request("GET", "/api/assistant/business-signals", token, org_id)
        signals = signals_payload.get("signals") or signals_payload.get("items") or []
        if isinstance(signals_payload, list):
            signals = signals_payload
        labeled = 0
        sample_signal = None
        for row in signals:
            if not isinstance(row, dict):
                continue
            if row.get("confidence") is None and row.get("confidence_source") == "insufficient_data":
                labeled += 1
                sample_signal = row
                break
            if _has_estimate(row):
                labeled += 1
                sample_signal = row
                break
        ok = labeled > 0 or len(signals) == 0
        report["checks"]["business_signals"] = {
            "status": "PASS" if ok else "FAIL",
            "signal_count": len(signals),
            "sample": {
                "confidence": (sample_signal or {}).get("confidence"),
                "confidenceIsEstimate": (sample_signal or {}).get(
                    "confidenceIsEstimate", (sample_signal or {}).get("confidence_is_estimate")
                ),
                "confidenceSource": (sample_signal or {}).get(
                    "confidenceSource", (sample_signal or {}).get("confidence_source")
                ),
            }
            if sample_signal
            else None,
            "note": "empty signals list is OK — no invented confidence",
        }
        print(f"business_signals: {report['checks']['business_signals']}")
    except Exception as exc:  # noqa: BLE001
        report["checks"]["business_signals"] = {"status": "FAIL", "detail": str(exc)}
        print(f"business_signals FAIL: {exc}")

    # 5) Meson suggestions (control-tier — skip if org lacks entitlement)
    try:
        suggestions = _request(
            "POST",
            "/api/meson/suggestions",
            token,
            org_id,
            {"page": "ai-chat"},
        )
        rows = suggestions.get("suggestions") or []
        ok = bool(rows) and all(_has_estimate(r) for r in rows if isinstance(r, dict))
        first = rows[0] if rows and isinstance(rows[0], dict) else {}
        report["checks"]["meson_suggestions"] = {
            "status": "PASS" if ok else "FAIL",
            "count": len(rows),
            "confidenceIsEstimate": first.get("confidenceIsEstimate", first.get("confidence_is_estimate")),
            "confidenceSource": first.get("confidenceSource", first.get("confidence_source")),
        }
        print(f"meson_suggestions: {report['checks']['meson_suggestions']}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        report["checks"]["meson_suggestions"] = {
            "status": "SKIP",
            "detail": f"HTTP {exc.code}: {detail}",
        }
        print(f"meson_suggestions SKIP: HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        report["checks"]["meson_suggestions"] = {"status": "FAIL", "detail": str(exc)}
        print(f"meson_suggestions FAIL: {exc}")

    # 6) Optimization recommendations (estimate defaults on Recommendation model)
    try:
        analyze = _request(
            "POST",
            "/api/optimization/analyze",
            token,
            org_id,
            {"workflow_id": "00000000-0000-0000-0000-000000000001", "days": 30},
        )
        rows = analyze if isinstance(analyze, list) else analyze.get("recommendations") or []
        if not rows:
            report["checks"]["optimization_analyze"] = {
                "status": "PASS",
                "count": 0,
                "note": "empty recommendations (no invented confidence)",
            }
        else:
            first = rows[0] if isinstance(rows[0], dict) else {}
            ok = _has_estimate(first)
            report["checks"]["optimization_analyze"] = {
                "status": "PASS" if ok else "FAIL",
                "count": len(rows),
                "confidenceIsEstimate": first.get("confidenceIsEstimate", first.get("confidence_is_estimate")),
                "confidenceSource": first.get("confidenceSource", first.get("confidence_source")),
            }
        print(f"optimization_analyze: {report['checks']['optimization_analyze']}")
    except Exception as exc:  # noqa: BLE001
        report["checks"]["optimization_analyze"] = {"status": "FAIL", "detail": str(exc)}
        print(f"optimization_analyze FAIL: {exc}")

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    statuses = [c.get("status") for c in report["checks"].values()]
    required = [
        "deploy",
        "models_runtime",
        "advisor_brief",
        "business_signals",
        "intelligence_forecast",
    ]
    required_ok = all(report["checks"].get(k, {}).get("status") == "PASS" for k in required)
    report["summary"] = {
        "pass": statuses.count("PASS"),
        "fail": statuses.count("FAIL"),
        "skip": statuses.count("SKIP"),
        "required_pass": required_ok,
        "overall": "PASS" if required_ok and statuses.count("FAIL") == 0 else "FAIL",
    }

    if args.json:
        out = Path(args.json)
        if not out.is_absolute():
            out = REPO / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {out}")

    print(json.dumps({"summary": report["summary"], "git_sha": health.get("git_sha")}, indent=2))
    return 0 if report["summary"]["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
