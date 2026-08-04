#!/usr/bin/env python3
"""Live proof for extension v2 Salesforce + Slack *surfaces*.

Uses tip-org HubSpot/Apollo for enrich + approved write (same gate as careers_about).
Native salesforce.leads.* / slack.users.info run only when those connectors are connected —
surface proof does not require them; page_url + detect_surface must be SF/Slack.
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

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "browser-extension-v2-sf-slack-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
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


def _prove_surface(
    *,
    ctx,
    client,
    surface: str,
    page_url: str,
    page_context: dict,
    connected: list[str],
) -> dict:
    from app.services.extension_bridge_service import (
        detect_surface,
        enrich_from_page_context,
        execute_extension_action,
    )
    from app.routers.business_outcomes import _project_from_run

    cases: dict = {}
    detected = detect_surface(page_url, page_context)
    cases["detect"] = {
        "status": "PASS" if detected == surface else "FAIL",
        "expected": surface,
        "got": detected,
    }

    enrich = enrich_from_page_context(
        ctx,
        page_url=page_url,
        page_context=page_context,
        connected=connected,
    )
    match_actions = [m.get("action") for m in (enrich.get("matches") or [])]
    cases["enrich"] = {
        "status": "PASS"
        if enrich.get("surface") == surface and (enrich.get("matches") or enrich.get("suggestions"))
        else "FAIL",
        "surface": enrich.get("surface"),
        "matchActions": match_actions,
        "suggestionCount": len(enrich.get("suggestions") or []),
        "nativeSlackRead": "slack.users.info" in match_actions,
        "nativeSalesforceRead": "salesforce.leads.search" in match_actions,
    }

    stamp = datetime.now(timezone.utc).strftime("%H%M%S")
    list_name = f"Extension v2 {surface} {stamp}-{uuid.uuid4().hex[:6]}"
    propose = execute_extension_action(
        ctx,
        org_id=ORG,
        user_id=ACTOR,
        action="hubspot.lists.create",
        params={"name": list_name},
        page_url=page_url,
        confirmation_token=None,
    )
    token = propose.get("confirmationToken")
    cases["propose"] = {
        "status": "PASS" if propose.get("status") == "needs_confirmation" and token else "FAIL",
        "approvalId": propose.get("approvalId"),
    }
    if not token:
        cases["confirm_write"] = {"status": "FAIL", "error": "no confirmationToken"}
        cases["outcomes"] = {"status": "FAIL"}
        cases["notification"] = {"status": "FAIL"}
        return cases

    result = execute_extension_action(
        ctx,
        org_id=ORG,
        user_id=ACTOR,
        action=None,
        params={},
        page_url=page_url,
        confirmation_token=token,
    )
    run_id = result.get("runId")
    cases["confirm_write"] = {
        "status": "PASS" if result.get("success") and run_id else "FAIL",
        "runId": run_id,
        "success": result.get("success"),
        "error": result.get("error"),
    }

    dto = _project_from_run(client, ORG, run_id, "production") if run_id else None
    cases["outcomes"] = {
        "status": "PASS"
        if dto and dto.get("source") == "browser_extension" and dto.get("status") == "completed"
        else "FAIL",
        "businessOutcomeDto": {
            "id": (dto or {}).get("id"),
            "source": (dto or {}).get("source"),
            "status": (dto or {}).get("status"),
        }
        if dto
        else None,
        "openUrl": f"https://gravitre.app/outcomes/{run_id}" if run_id else None,
    }

    notif = (
        (
            client.table("notifications")
            .select("id, entity_id")
            .eq("org_id", ORG)
            .eq("entity_id", run_id)
            .eq("type", "run_completed")
            .limit(1)
            .execute()
            .data
            or []
        )
        if run_id
        else []
    )
    cases["notification"] = {
        "status": "PASS" if notif else "FAIL",
        "notificationId": (notif[0] or {}).get("id") if notif else None,
    }
    return cases


def main() -> int:
    _load_env()
    from supabase import create_client

    from app.config import get_settings
    from app.services.extension_bridge_service import connected_integrations
    from app.services.tool_types import ToolContext

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=ORG,
        actor_id=ACTOR,
        environment_name="production",
    )
    connected = connected_integrations(client, ORG)
    evidence: dict = {
        "startedAt": utcnow(),
        "orgId": ORG,
        "connected": connected,
        "surfaces": {},
    }

    evidence["surfaces"]["salesforce"] = _prove_surface(
        ctx=ctx,
        client=client,
        surface="salesforce",
        page_url="https://acme.lightning.force.com/lightning/r/Lead/00Q000000000001/view",
        page_context={
            "fullName": "Jordan ExtSF",
            "email": "jordan.extsf@acme-example.com",
            "company": "Acme Example",
            "title": "Operator",
            "source": "salesforce",
        },
        connected=connected,
    )

    evidence["surfaces"]["slack"] = _prove_surface(
        ctx=ctx,
        client=client,
        surface="slack",
        page_url="https://app.slack.com/client/T00000000/user_profile/U0EXTSLACK",
        page_context={
            "fullName": "Casey ExtSlack",
            "email": "casey.extslack@acme-example.com",
            "company": "Acme Example",
            "title": "Partner",
            "slackUserId": "U0EXTSLACK",
            "source": "slack",
        },
        connected=connected,
    )

    evidence["finishedAt"] = utcnow()
    all_statuses = [
        c.get("status")
        for surface in evidence["surfaces"].values()
        for c in surface.values()
    ]
    evidence["overall"] = "PASS" if all_statuses and all(s == "PASS" for s in all_statuses) else "FAIL"
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
