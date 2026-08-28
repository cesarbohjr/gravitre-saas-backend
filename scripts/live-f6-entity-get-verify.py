#!/usr/bin/env python3
"""F6 live proof: the follow_up_entity_get adapter against a real vendor.

Everything else about this adapter has been proven locally with mocks, which
cannot show that the declared sibling GET actually reaches HubSpot. So:

  1. Create one disposable contact in the isolated smoke org (real write).
  2. verify_entity_get -> must return follow_up_entity_get_confirmed.
  3. NEGATIVE CONTROL: same call with a fabricated id that was never written.
     If that also "verifies", the adapter is vacuous and step 2 means nothing.
  4. Delete the contact so the org is left clean.

Writes docs/delivery/f6-entity-get-verify-live.json
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

# Same isolated smoke org the F6 membership proof uses — never a customer org.
ORG = os.environ.get("F6_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")
ACTOR = os.environ.get("F6_ACTOR_ID", "a9f1240f-910a-42ca-aebf-38caeac288c3")
OUT = REPO / "docs" / "delivery" / "f6-entity-get-verify-live.json"

WRITE_ACTION = "hubspot.contacts.create"
DELETE_ACTION = "hubspot.contacts.delete"


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
        from supabase import create_client

        from app.config import get_settings

        _SETTINGS = get_settings()
        _SB = create_client(_SETTINGS.supabase_url, _SETTINGS.supabase_service_role_key)
    return _SB


def _connector_id(vendor: str) -> str | None:
    rows = (
        _sb()
        .table("connectors")
        .select("id, type, status")
        .eq("org_id", ORG)
        .eq("type", vendor)
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    for row in rows:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            return str(row["id"])
    return None


def main() -> int:
    _load_env()
    import httpx

    from app.config import get_settings
    from app.services.entity_get_verify import extract_entity_id, verify_entity_get
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    report: dict = {
        "started_at": utcnow(),
        "org_id": ORG,
        "vendor": "hubspot",
        "write_action": WRITE_ACTION,
        "pass": False,
    }

    try:
        report["live_git_sha"] = (
            httpx.get("https://api.gravitre.app/health", timeout=60).json().get("git_sha")
        )
    except Exception as exc:  # noqa: BLE001
        report["live_git_sha"] = f"unreachable:{exc.__class__.__name__}"

    connector_id = _connector_id("hubspot")
    report["connector_id"] = connector_id
    if not connector_id:
        report["blocker"] = "no_active_hubspot_connector_in_smoke_org"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    ctx = ToolContext(
        settings=_SETTINGS or get_settings(),
        client=_sb(),
        org_id=ORG,
        actor_id=ACTOR,
        connector_id=connector_id,
    )

    marker = uuid.uuid4().hex[:12]
    email = f"f6.entityget.{marker}@gravitre-smoke.example.com"
    report["test_contact_email"] = email

    write = invoke_tool(
        ctx,
        WRITE_ACTION,
        {
            "connector_id": connector_id,
            "properties": {
                "email": email,
                "firstname": "F6",
                "lastname": f"EntityGet {marker}",
            },
        },
    )
    report["write"] = {
        "success": bool(write.success),
        "error_code": getattr(write, "error_code", None),
        "error_message": (getattr(write, "error_message", None) or "")[:300] or None,
    }
    if not write.success:
        report["blocker"] = "live_write_failed"
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    result_data = write.data if isinstance(write.data, dict) else {}
    entity_id = extract_entity_id(result_data, "id")
    report["written_entity_id"] = entity_id

    positive = verify_entity_get(
        invoke_action=WRITE_ACTION, result_data=result_data, ctx=ctx, settle=True
    )
    report["positive"] = positive.as_dict()

    # The control: an id HubSpot has never issued. Must not verify.
    fake_id = "99" + uuid.uuid4().int.__str__()[:12]
    negative = verify_entity_get(
        invoke_action=WRITE_ACTION,
        result_data={"id": fake_id},
        ctx=ctx,
        settle=False,
    )
    report["negative_control"] = {"fabricated_id": fake_id, **negative.as_dict()}

    cleanup = None
    if entity_id:
        try:
            d = invoke_tool(
                ctx, DELETE_ACTION, {"connector_id": connector_id, "contact_id": entity_id}
            )
            cleanup = {"success": bool(d.success), "error": (d.error_message or "")[:200] or None}
        except Exception as exc:  # noqa: BLE001
            cleanup = {"success": False, "error": f"{exc.__class__.__name__}: {exc}"}
    report["cleanup_deleted_test_contact"] = cleanup

    report["pass"] = bool(positive.verified and not negative.verified)
    report["verdict"] = (
        "PASS — live vendor read-back confirmed the written id, and a fabricated id "
        "was correctly refused."
        if report["pass"]
        else "FAIL — see positive/negative_control."
    )
    report["finished_at"] = utcnow()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
