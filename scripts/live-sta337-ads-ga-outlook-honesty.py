#!/usr/bin/env python3
"""STA-337 live evidence: Google Ads + Microsoft 365 (+ GA if connected).

Uses LOCAL invoke_tool against smoke-org connectors (same pattern as
live-list-populate-honesty.py). Writes docs/delivery/sta337-live-evidence.json.

Pass bar (per connected connector):
  - tool.invoke.completed audit_event with action name
  - verified vendor evidence fields (entity ids / result_url / accepted_async stamp)
  - mutating pause/resume restored to prior status when possible
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
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
OUT = REPO / "docs" / "delivery" / "sta337-live-evidence.json"

# Prefer reversible Ads mutate: pause an ENABLED campaign then resume.
ALLOW_ADS_MUTATE = os.environ.get("STA337_ALLOW_ADS_MUTATE", "1") == "1"
# Mail send is real vendor side-effect; default on but only to actor email.
ALLOW_MAIL_SEND = os.environ.get("STA337_ALLOW_MAIL_SEND", "1") == "1"


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
            if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
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
        "error_message": (invoke.error_message or "")[:240],
        "action_stamp": getattr(invoke, "action", None) or data.get("action"),
        "data_keys": sorted(data.keys()) if data else [],
        "result_url": data.get("result_url") or data.get("external_url"),
        "accepted_async": data.get("accepted_async"),
        "outcome_effect": data.get("outcome_effect"),
        "entity_id": data.get("id") or data.get("campaign_id") or data.get("message_id"),
        "raw_snippet": {k: data[k] for k in list(data)[:12]} if data else {},
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
        .limit(80)
        .execute()
    ).data or []
    out = []
    n = needle.lower()
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        blob = json.dumps(meta, default=str).lower()
        if n in blob or n in str(row.get("action") or "").lower():
            out.append(
                {
                    "id": row.get("id"),
                    "action": row.get("action"),
                    "created_at": row.get("created_at"),
                    "tool": meta.get("tool") or meta.get("tool_name") or meta.get("action"),
                }
            )
    return out


def _actor_email() -> str | None:
    try:
        row = (
            _sb()
            .table("profiles")
            .select("email")
            .eq("id", ACTOR)
            .limit(1)
            .execute()
        ).data or []
        if row and row[0].get("email"):
            return str(row[0]["email"])
    except Exception:  # noqa: BLE001
        pass
    try:
        # auth.users via RPC-less fallback — users table if present
        row = (
            _sb()
            .table("users")
            .select("email")
            .eq("id", ACTOR)
            .limit(1)
            .execute()
        ).data or []
        if row and row[0].get("email"):
            return str(row[0]["email"])
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get("STA337_MAIL_TO") or os.environ.get("SMOKE_MAIL_TO")


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
        "generated_at": started,
        "prod_tip_at_run": tip,
        "org_id": ORG,
        "actor_id": ACTOR,
        "live_pass_claimed": False,
        "connectors": {},
        "invokes": {},
        "audits": {},
        "verdicts": {},
        "notes": [],
    }

    ads = _connector(["google_ads", "googleads"])
    ga = _connector(["google_analytics", "ga4", "analytics"])
    m365 = _connector(["microsoft365", "microsoft", "outlook"])
    evidence["connectors"] = {
        "google_ads": {"id": ads["id"], "type": ads["type"], "status": ads["status"]} if ads else None,
        "google_analytics": {"id": ga["id"], "type": ga["type"], "status": ga["status"]} if ga else None,
        "microsoft365": {"id": m365["id"], "type": m365["type"], "status": m365["status"]} if m365 else None,
    }

    # --- Google Ads ---
    if not ads:
        evidence["verdicts"]["google_ads"] = "NOT RUN — no healthy connector in smoke org"
    else:
        cid = str(ads["id"])
        list_inv = _invoke("googleads.campaigns.list", {}, cid)
        evidence["invokes"]["googleads.campaigns.list"] = _summarize(list_inv)
        campaigns = []
        if isinstance(list_inv.data, dict):
            campaigns = list_inv.data.get("campaigns") or list_inv.data.get("results") or []
            if not isinstance(campaigns, list):
                campaigns = []

        mutate_target = None
        prior_status = None
        for c in campaigns:
            if not isinstance(c, dict):
                continue
            status = str(c.get("status") or c.get("campaignStatus") or "").upper()
            camp_id = str(c.get("id") or c.get("campaign_id") or "").strip()
            if camp_id and status == "ENABLED":
                mutate_target = camp_id
                prior_status = "ENABLED"
                break
        if not mutate_target:
            for c in campaigns:
                if not isinstance(c, dict):
                    continue
                status = str(c.get("status") or c.get("campaignStatus") or "").upper()
                camp_id = str(c.get("id") or c.get("campaign_id") or "").strip()
                if camp_id and status == "PAUSED":
                    mutate_target = camp_id
                    prior_status = "PAUSED"
                    break

        evidence["invokes"]["googleads.campaigns.list"]["campaign_count"] = len(campaigns)
        evidence["invokes"]["googleads.campaigns.list"]["mutate_target"] = mutate_target
        evidence["invokes"]["googleads.campaigns.list"]["prior_status"] = prior_status

        if ALLOW_ADS_MUTATE and mutate_target and prior_status == "ENABLED":
            pause = _invoke("googleads.campaigns.pause", {"campaign_id": mutate_target}, cid)
            evidence["invokes"]["googleads.campaigns.pause"] = _summarize(pause)
            resume = _invoke("googleads.campaigns.resume", {"campaign_id": mutate_target}, cid)
            evidence["invokes"]["googleads.campaigns.resume"] = _summarize(resume)
        elif ALLOW_ADS_MUTATE and mutate_target and prior_status == "PAUSED":
            resume = _invoke("googleads.campaigns.resume", {"campaign_id": mutate_target}, cid)
            evidence["invokes"]["googleads.campaigns.resume"] = _summarize(resume)
            pause = _invoke("googleads.campaigns.pause", {"campaign_id": mutate_target}, cid)
            evidence["invokes"]["googleads.campaigns.pause"] = _summarize(pause)
        else:
            evidence["notes"].append(
                "Ads mutate skipped — no campaign id from list or STA337_ALLOW_ADS_MUTATE=0"
            )

        evidence["audits"]["google_ads"] = _audit_since(started, "googleads")
        pause_ok = bool((evidence["invokes"].get("googleads.campaigns.pause") or {}).get("success"))
        resume_ok = bool((evidence["invokes"].get("googleads.campaigns.resume") or {}).get("success"))
        list_ok = bool(evidence["invokes"]["googleads.campaigns.list"].get("success"))
        audit_ok = any(a.get("action") == "tool.invoke.completed" for a in evidence["audits"]["google_ads"])
        if pause_ok and resume_ok and audit_ok:
            evidence["verdicts"]["google_ads"] = "PASS"
        elif list_ok and audit_ok:
            evidence["verdicts"]["google_ads"] = "PARTIAL — list ok; mutate incomplete"
        else:
            evidence["verdicts"]["google_ads"] = "FAIL"

    # --- Google Analytics ---
    if not ga:
        evidence["verdicts"]["google_analytics"] = "NOT RUN — no google_analytics/ga4 connector in any smoke path"
        evidence["notes"].append("Prod has zero google_analytics connectors (org-wide check prior).")
    else:
        cid = str(ga["id"])
        inv = _invoke("analytics.reports.run", {"metrics": ["sessions"], "dimensions": ["date"]}, cid)
        evidence["invokes"]["analytics.reports.run"] = _summarize(inv)
        evidence["audits"]["google_analytics"] = _audit_since(started, "analytics")
        audit_ok = any(a.get("action") == "tool.invoke.completed" for a in evidence["audits"]["google_analytics"])
        evidence["verdicts"]["google_analytics"] = (
            "PASS" if inv.success and audit_ok else "FAIL"
        )

    # --- Microsoft 365 / Outlook alias ---
    if not m365:
        evidence["verdicts"]["microsoft365"] = "NOT RUN — no healthy microsoft365 connector"
    else:
        cid = str(m365["id"])
        # Write with entity id (safer than mail): short calendar event then leave as evidence.
        start = datetime.now(timezone.utc) + timedelta(days=14)
        end = start + timedelta(hours=1)
        cal = _invoke(
            "microsoft365.calendar.events.create",
            {
                "subject": f"STA-337 honesty probe {uuid.uuid4().hex[:8]}",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "body": "Automated STA-337 completed-work honesty probe. Safe to delete.",
            },
            cid,
        )
        evidence["invokes"]["microsoft365.calendar.events.create"] = _summarize(cal)

        mail_to = _actor_email()
        evidence["mail_to"] = mail_to
        if ALLOW_MAIL_SEND and mail_to:
            # Alias path (outlook → microsoft365) + native send.
            alias = _invoke(
                "outlook.messages.send",
                {
                    "to": [mail_to],
                    "subject": f"STA-337 honesty probe {uuid.uuid4().hex[:8]}",
                    "body": "Automated STA-337 Outlook→M365 alias send probe. Safe to ignore.",
                },
                cid,
            )
            evidence["invokes"]["outlook.messages.send"] = _summarize(alias)
            native = _invoke(
                "microsoft365.mail.send",
                {
                    "to": [mail_to],
                    "subject": f"STA-337 M365 native send {uuid.uuid4().hex[:8]}",
                    "body": "Automated STA-337 microsoft365.mail.send probe. Safe to ignore.",
                },
                cid,
            )
            evidence["invokes"]["microsoft365.mail.send"] = _summarize(native)
        else:
            evidence["notes"].append(
                "Mail send skipped — no actor email / STA337_MAIL_TO and STA337_ALLOW_MAIL_SEND"
            )

        evidence["audits"]["microsoft365"] = _audit_since(started, "microsoft365") + _audit_since(
            started, "outlook"
        )
        # de-dupe audits by id
        seen = set()
        deduped = []
        for a in evidence["audits"]["microsoft365"]:
            if a["id"] in seen:
                continue
            seen.add(a["id"])
            deduped.append(a)
        evidence["audits"]["microsoft365"] = deduped

        cal_ok = bool(evidence["invokes"]["microsoft365.calendar.events.create"].get("success"))
        send = evidence["invokes"].get("microsoft365.mail.send") or evidence["invokes"].get(
            "outlook.messages.send"
        )
        send_ok = bool(send and send.get("success"))
        stamp_ok = bool(
            send
            and (
                send.get("accepted_async")
                or send.get("result_url")
                or send.get("entity_id")
            )
        )
        audit_ok = any(a.get("action") == "tool.invoke.completed" for a in evidence["audits"]["microsoft365"])
        if cal_ok and send_ok and stamp_ok and audit_ok:
            evidence["verdicts"]["microsoft365"] = "PASS"
        elif cal_ok and audit_ok:
            evidence["verdicts"]["microsoft365"] = "PARTIAL — calendar write ok; mail send incomplete"
        else:
            evidence["verdicts"]["microsoft365"] = "FAIL"

    # Overall: only claim live PASS when Ads mutate + M365 send both PASS; GA may remain NOT RUN.
    ads_v = evidence["verdicts"].get("google_ads", "")
    m365_v = evidence["verdicts"].get("microsoft365", "")
    ga_v = evidence["verdicts"].get("google_analytics", "")
    evidence["live_pass_claimed"] = ads_v == "PASS" and m365_v == "PASS"
    evidence["overall"] = {
        "google_ads": ads_v,
        "google_analytics": ga_v,
        "microsoft365": m365_v,
        "live_pass_claimed": evidence["live_pass_claimed"],
        "honesty_gates_still_required_for_ga": ga_v.startswith("NOT RUN"),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(evidence["overall"], indent=2))
    print(f"wrote {OUT}")
    return 0 if evidence["live_pass_claimed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
