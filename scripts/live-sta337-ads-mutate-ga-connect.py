#!/usr/bin/env python3
"""STA-337 follow-up: Ads pause/resume on a PAUSED test campaign + GA connect/report.

1) googleads.structure.create (PAUSED) → resume → pause (restore)
2) Ensure google_analytics connector + print OAuth URL if disconnected
3) If connected, analytics.reports.run + audit pointer

Writes docs/delivery/sta337-ads-mutate-ga-live.json
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = os.environ.get("SMOKE_ORG_ID", "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea")
ACTOR = os.environ.get("SMOKE_ACTOR_ID", "f7e32f06-49df-4e73-8962-f41c21850762")
OUT = REPO / "docs" / "delivery" / "sta337-ads-mutate-ga-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


_SB = None
_SETTINGS = None


def _sb():
    global _SB, _SETTINGS
    if _SB is None:
        from app.config import get_settings
        from supabase import create_client

        _SETTINGS = get_settings()
        _SB = create_client(_SETTINGS.supabase_url, _SETTINGS.supabase_service_role_key)
    return _SB


def _connector(types: list[str]) -> dict | None:
    for t in types:
        rows = (
            _sb()
            .table("connectors")
            .select("id, type, status, config")
            .eq("org_id", ORG)
            .eq("type", t)
            .is_("deleted_at", "null")
            .limit(5)
            .execute()
        ).data or []
        for row in rows:
            if str(row.get("status") or "").lower() in {
                "active",
                "connected",
                "healthy",
                "needs_connection",
            }:
                return row
    return None


def _invoke(action: str, params: dict, connector_id: str | None):
    from app.config import get_settings
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    ctx = ToolContext(
        settings=_SETTINGS or get_settings(),
        client=_sb(),
        org_id=ORG,
        actor_id=ACTOR,
        connector_id=connector_id,
    )
    payload = dict(params)
    if connector_id:
        payload.setdefault("connector_id", connector_id)
    return invoke_tool(ctx, action, payload)


def _summarize(invoke) -> dict:
    data = invoke.data if isinstance(invoke.data, dict) else {}
    return {
        "success": bool(invoke.success),
        "error_code": invoke.error_code,
        "error_message": (invoke.error_message or "")[:400],
        "action_stamp": getattr(invoke, "action", None),
        "data_keys": sorted(data.keys()) if data else [],
        "result_url": data.get("result_url") or data.get("external_url") or data.get("webLink"),
        "accepted_async": data.get("accepted_async"),
        "outcome_effect": data.get("outcome_effect"),
        "entity_id": data.get("id") or data.get("campaign_id") or data.get("entity_id"),
        "snippet": {k: data.get(k) for k in list(data)[:14]} if data else {},
    }


def _audit_since(started: str, needle: str) -> list[dict]:
    rows = (
        _sb()
        .table("audit_events")
        .select("id, action, created_at, metadata")
        .eq("org_id", ORG)
        .gte("created_at", started)
        .in_("action", ["tool.invoke.completed", "tool.invoke.failed", "tool.invoke.requested"])
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    ).data or []
    out = []
    n = needle.lower()
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        blob = json.dumps(meta, default=str).lower()
        if n in blob:
            out.append(
                {
                    "id": row.get("id"),
                    "action": row.get("action"),
                    "created_at": row.get("created_at"),
                    "tool": meta.get("tool") or meta.get("tool_name") or meta.get("action"),
                }
            )
    return out


def _ensure_ga_connector() -> dict:
    """Create or reuse a google_analytics connector row for smoke org."""
    from app.connectors.repository import create_connector

    existing = _connector(["google_analytics", "ga4"])
    if existing:
        return existing
    created = create_connector(
        _sb(),
        ORG,
        "google_analytics",
        {"label": "STA-337 GA4 smoke", "auth_mode": "oauth"},
        ACTOR,
        "production",
        status="needs_connection",
    )
    return created


def _mint_smoke_jwt() -> str:
    import time

    import jwt as pyjwt

    secret = os.environ.get("SUPABASE_JWT_SECRET") or ""
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    email = os.environ.get("SMOKE_EMAIL") or "cesar.bohorquez.jr@gmail.com"
    if not secret or not url:
        raise RuntimeError("SUPABASE_JWT_SECRET / SUPABASE_URL required to mint smoke JWT")
    now = int(time.time())
    return pyjwt.encode(
        {
            "sub": ACTOR,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _ga_oauth_url(connector_id: str) -> dict:
    """Start OAuth via API so signed state is valid for callback."""
    try:
        token = os.environ.get("SMOKE_JWT") or os.environ.get("GRAVITRE_SMOKE_JWT") or _mint_smoke_jwt()
    except Exception as exc:  # noqa: BLE001
        return {"authorize_url": None, "error": f"jwt: {exc}"}
    try:
        r = httpx.post(
            f"{BASE}/api/connectors/oauth/google_analytics/start",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "name": "STA-337 GA4 smoke",
                "connectorId": connector_id,
                "redirectPath": "/connectors",
            },
            timeout=60.0,
        )
        body = r.json() if r.content else {}
        return {
            "authorize_url": body.get("authorizationUrl")
            or body.get("authorization_url")
            or body.get("authorizeUrl"),
            "connector_id": body.get("connectorId") or body.get("connector_id") or connector_id,
            "state_prefix": str(body.get("state") or "")[:24],
            "http_status": r.status_code,
            "body_error": body.get("detail") or body.get("error") or body.get("message"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"authorize_url": None, "error": str(exc)}


def main() -> int:
    _load_env()
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_error:{exc}"

    started = utcnow()
    evidence: dict = {
        "ticket": "STA-337",
        "probe": "ads_mutate_and_ga_connect",
        "generated_at": started,
        "prod_tip_at_run": tip,
        "org_id": ORG,
        "invokes": {},
        "audits": {},
        "verdicts": {},
        "ga_oauth": None,
        "notes": [],
    }

    # ----- Google Ads mutate -----
    ads = _connector(["google_ads", "googleads"])
    if not ads or str(ads.get("status") or "").lower() not in {"active", "connected", "healthy"}:
        evidence["verdicts"]["google_ads"] = "FAIL — no healthy google_ads connector"
    else:
        cid = str(ads["id"])
        suffix = uuid.uuid4().hex[:8]
        create = _invoke(
            "googleads.structure.create",
            {
                "daily_budget_total": 1.0,
                "status": "PAUSED",
                "campaigns": [
                    {
                        "name": f"STA337 honesty {suffix}",
                        "budget_weight": 1.0,
                        "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                        "ad_groups": [
                            {
                                "name": f"STA337 AG {suffix}",
                                "keywords": [
                                    {"text": f"sta337 probe {suffix}", "match_type": "EXACT"}
                                ],
                            }
                        ],
                    }
                ],
            },
            cid,
        )
        evidence["invokes"]["googleads.structure.create"] = _summarize(create)
        campaign_id = None
        if create.success and isinstance(create.data, dict):
            camps = create.data.get("campaigns") or []
            if camps and isinstance(camps[0], dict):
                campaign_id = str(camps[0].get("campaign_id") or camps[0].get("id") or "") or None
                evidence["invokes"]["googleads.structure.create"]["campaign_id"] = campaign_id
                evidence["invokes"]["googleads.structure.create"]["campaign_result_url"] = camps[
                    0
                ].get("result_url")

        if campaign_id:
            # Created PAUSED → resume then pause (prove both mutates; leave paused).
            resume = _invoke("googleads.campaigns.resume", {"campaign_id": campaign_id}, cid)
            evidence["invokes"]["googleads.campaigns.resume"] = _summarize(resume)
            pause = _invoke("googleads.campaigns.pause", {"campaign_id": campaign_id}, cid)
            evidence["invokes"]["googleads.campaigns.pause"] = _summarize(pause)
        else:
            evidence["notes"].append("structure.create did not return campaign_id")

        evidence["audits"]["google_ads"] = (
            _audit_since(started, "googleads") + _audit_since(started, "google_ads")
        )
        seen = set()
        deduped = []
        for a in evidence["audits"]["google_ads"]:
            if a["id"] in seen:
                continue
            seen.add(a["id"])
            deduped.append(a)
        evidence["audits"]["google_ads"] = deduped

        create_ok = bool(evidence["invokes"]["googleads.structure.create"].get("success"))
        resume_ok = bool((evidence["invokes"].get("googleads.campaigns.resume") or {}).get("success"))
        pause_ok = bool((evidence["invokes"].get("googleads.campaigns.pause") or {}).get("success"))
        audit_ok = any(
            a.get("action") == "tool.invoke.completed"
            and "pause" in str(a.get("tool") or "").lower()
            or (
                a.get("action") == "tool.invoke.completed"
                and "resume" in str(a.get("tool") or "").lower()
            )
            for a in evidence["audits"]["google_ads"]
        )
        # clearer audit check
        audit_pause = any(
            a.get("action") == "tool.invoke.completed" and "pause" in str(a.get("tool") or "")
            for a in evidence["audits"]["google_ads"]
        )
        audit_resume = any(
            a.get("action") == "tool.invoke.completed" and "resume" in str(a.get("tool") or "")
            for a in evidence["audits"]["google_ads"]
        )
        if create_ok and resume_ok and pause_ok and audit_pause and audit_resume:
            evidence["verdicts"]["google_ads"] = "PASS"
        elif create_ok and (resume_ok or pause_ok):
            evidence["verdicts"]["google_ads"] = "PARTIAL — create ok; mutate incomplete"
        else:
            evidence["verdicts"]["google_ads"] = "FAIL"

    # ----- Google Analytics -----
    ga = _ensure_ga_connector()
    evidence["ga_connector"] = {
        "id": ga.get("id"),
        "type": ga.get("type"),
        "status": ga.get("status"),
        "property_id": (ga.get("config") or {}).get("property_id")
        or (ga.get("config") or {}).get("propertyId"),
    }
    ga_id = str(ga["id"])
    status = str(ga.get("status") or "").lower()
    if status not in {"active", "connected", "healthy"}:
        evidence["ga_oauth"] = _ga_oauth_url(ga_id)
        evidence["verdicts"]["google_analytics"] = (
            "BLOCKED — connector needs OAuth; open authorize_url then re-run"
        )
        evidence["notes"].append(
            "Open ga_oauth.authorize_url while signed into the Google account that owns a GA4 property, "
            "then re-run this script."
        )
    else:
        report = _invoke(
            "analytics.reports.run",
            {
                "metrics": ["sessions", "activeUsers"],
                "dimensions": ["date"],
                "start_date": "7daysAgo",
                "end_date": "yesterday",
            },
            ga_id,
        )
        evidence["invokes"]["analytics.reports.run"] = _summarize(report)
        evidence["audits"]["google_analytics"] = _audit_since(started, "analytics")
        audit_ok = any(
            a.get("action") == "tool.invoke.completed" for a in evidence["audits"]["google_analytics"]
        )
        evidence["verdicts"]["google_analytics"] = (
            "PASS" if report.success and audit_ok else "FAIL"
        )

    evidence["live_pass_claimed"] = (
        evidence["verdicts"].get("google_ads") == "PASS"
        and evidence["verdicts"].get("google_analytics") == "PASS"
    )
    evidence["overall"] = {
        "google_ads": evidence["verdicts"].get("google_ads"),
        "google_analytics": evidence["verdicts"].get("google_analytics"),
        "live_pass_claimed": evidence["live_pass_claimed"],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(evidence["overall"], indent=2))
    if evidence.get("ga_oauth"):
        print("GA_OAUTH_URL=" + evidence["ga_oauth"].get("authorize_url", ""))
    print(f"wrote {OUT}")
    return 0 if evidence["live_pass_claimed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
