#!/usr/bin/env python3
"""Live proof for extension v2: careers_about enrich + approved write + Outcomes + usage signal."""
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
OUT = REPO / "docs" / "delivery" / "browser-extension-v2-live.json"


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


def main() -> int:
    _load_env()
    from supabase import create_client

    from app.config import get_settings
    from app.services.extension_bridge_service import (
        connected_integrations,
        detect_surface,
        enrich_from_page_context,
        execute_extension_action,
        record_extension_usage_signal,
    )
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
    evidence: dict = {"startedAt": utcnow(), "orgId": ORG, "cases": {}}

    page_url = "https://www.acme-example.com/careers"
    assert detect_surface(page_url) == "careers_about"
    evidence["cases"]["detect_careers_about"] = {"status": "PASS", "surface": "careers_about"}

    # Usage signal for an outside-allowlist host (honest prioritization signal)
    outside = "https://totally-unknown-crm.example/leads/123"
    sig = record_extension_usage_signal(
        client,
        org_id=ORG,
        user_id=ACTOR,
        page_url=outside,
        surface=None,
        invoked=True,
        note="v2_smoke_outside_allowlist",
    )
    evidence["cases"]["usage_signal_outside"] = {
        "status": "PASS" if sig.get("ok") and not sig.get("host_allowlisted") else "FAIL",
        "surface": sig.get("surface"),
        "host_allowlisted": sig.get("host_allowlisted"),
    }

    connected = connected_integrations(client, ORG)
    enrich = enrich_from_page_context(
        ctx,
        page_url=page_url,
        page_context={
            "company": "Acme Example",
            "domain": "acme-example.com",
            "title": "Careers at Acme",
            "source": "careers_about",
        },
        connected=connected,
    )
    evidence["cases"]["careers_enrich"] = {
        "status": "PASS" if enrich.get("surface") == "careers_about" else "FAIL",
        "surface": enrich.get("surface"),
        "matchCount": len(enrich.get("matches") or []),
        "suggestionCount": len(enrich.get("suggestions") or []),
    }

    list_name = f"Extension v2 careers {datetime.now(timezone.utc).strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}"
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
    evidence["cases"]["propose"] = {
        "status": "PASS" if propose.get("status") == "needs_confirmation" and token else "FAIL",
        "approvalId": propose.get("approvalId"),
    }
    if not token:
        evidence["overall"] = "FAIL"
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 1

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
    evidence["cases"]["confirm_write"] = {
        "status": "PASS" if result.get("success") and run_id else "FAIL",
        "runId": run_id,
        "source": result.get("source"),
        "success": result.get("success"),
        "error": result.get("error"),
    }

    from app.routers.business_outcomes import _project_from_run

    dto = _project_from_run(client, ORG, run_id, "production") if run_id else None
    evidence["cases"]["outcomes"] = {
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
    evidence["cases"]["notification"] = {
        "status": "PASS" if notif else "FAIL",
        "notificationId": (notif[0] or {}).get("id") if notif else None,
    }

    evidence["finishedAt"] = utcnow()
    statuses = [c.get("status") for c in evidence["cases"].values()]
    evidence["overall"] = "PASS" if statuses and all(s == "PASS" for s in statuses) else "FAIL"
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
