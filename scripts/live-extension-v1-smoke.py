#!/usr/bin/env python3
"""Live proof: extension LinkedIn enrich → durable confirm token → write → Outcomes.

Runs LOCAL code against the smoke-org connectors (pre-merge), same pattern as
list-populate honesty. Does not trust client confirmed flags.

Evidence written to docs/delivery/browser-extension-v1-live.json
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "browser-extension-v1-live.json"
FOREIGN_ORG = "00000000-0000-0000-0000-000000000001"


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
            merged.update({k: v for k, v in merged.items() if v} if False else {k: v for k, v in loaded.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    from fastapi import HTTPException
    from supabase import create_client

    from app.auth.dependencies import get_org_context
    from app.config import get_settings
    from app.services.extension_bridge_service import (
        enrich_from_page_context,
        execute_extension_action,
        connected_integrations,
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
    evidence: dict = {
        "startedAt": utcnow(),
        "orgId": ORG,
        "actorId": ACTOR,
        "cases": {},
    }

    # --- Case 0: org boundary fail-loud (shared get_org_context) ---
    # Smoke actor is platform admin (only member on this org). Prove the shared
    # non-admin branch with real membership rows + is_platform_admin forced False.
    import asyncio
    from unittest.mock import patch
    from starlette.requests import Request

    async def _org_case() -> None:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/api/extension/session",
            "raw_path": b"/api/extension/session",
            "query_string": b"",
            "headers": [(b"x-org-id", FOREIGN_ORG.encode())],
            "client": ("127.0.0.1", 0),
            "server": ("test", 80),
        }
        request = Request(scope)
        user = {"user_id": ACTOR, "email": "smoke@gravitre.app"}
        # Platform-admin bypass still allowed (existing privilege).
        admin_org = await get_org_context(request, user, settings)
        with patch("app.auth.dependencies.is_platform_admin", return_value=False):
            try:
                await get_org_context(request, user, settings)
                evidence["cases"]["org_boundary_403"] = {
                    "status": "FAIL",
                    "detail": "expected HTTP 403 for non-admin non-member x-org-id",
                    "path": "app.auth.dependencies.get_org_context (shared)",
                }
            except HTTPException as exc:
                evidence["cases"]["org_boundary_403"] = {
                    "status": "PASS" if exc.status_code == 403 else "FAIL",
                    "statusCode": exc.status_code,
                    "detail": str(exc.detail),
                    "path": "app.auth.dependencies.get_org_context (shared)",
                    "note": (
                        "Smoke actor is platform_admin; non-admin branch forced via "
                        "is_platform_admin=False against live membership list. "
                        f"Platform-admin bypass still returns requested org={admin_org}."
                    ),
                }

    asyncio.run(_org_case())

    connected = connected_integrations(client, ORG)
    evidence["connectedIntegrations"] = connected
    if not connected:
        evidence["error"] = "No connected integrations on smoke org"
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 1

    # --- Case 1: LinkedIn-shaped enrich (same payload content script sends) ---
    page_url = "https://www.linkedin.com/in/extension-smoke-profile"
    page_context = {
        "fullName": "Extension Smoke Contact",
        "firstName": "Extension",
        "lastName": "Smoke",
        "title": "Operator QA",
        "company": "Gravitree Smoke Co",
        "linkedinUrl": page_url,
        "source": "linkedin",
    }
    enrich = enrich_from_page_context(
        ctx,
        page_url=page_url,
        page_context=page_context,
        connected=connected,
    )
    evidence["cases"]["linkedin_enrich"] = {
        "status": "PASS" if enrich.get("surface") == "linkedin" else "FAIL",
        "surface": enrich.get("surface"),
        "matchCount": len(enrich.get("matches") or []),
        "suggestionCount": len(enrich.get("suggestions") or []),
        "suggestions": [
            {"id": s.get("id"), "invokeAction": s.get("invokeAction")}
            for s in (enrich.get("suggestions") or [])
        ],
    }

    # --- Case 2: client confirmed:true without token cannot execute write ---
    # (API no longer accepts confirmed; missing token always stages.)
    propose = execute_extension_action(
        ctx,
        org_id=ORG,
        user_id=ACTOR,
        action="hubspot.lists.create" if "hubspot" in connected else "apollo.lists.create",
        params={
            "name": f"Extension smoke {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        },
        page_url=page_url,
        confirmation_token=None,
    )
    token = propose.get("confirmationToken")
    evidence["cases"]["propose_write_stages"] = {
        "status": "PASS"
        if propose.get("status") == "needs_confirmation" and token
        else "FAIL",
        "responseStatus": propose.get("status"),
        "hasConfirmationToken": bool(token),
        "approvalId": propose.get("approvalId"),
        "invokeAction": propose.get("invokeAction"),
    }

    forged = None
    try:
        execute_extension_action(
            ctx,
            org_id=ORG,
            user_id=ACTOR,
            action=None,
            params={},
            page_url=page_url,
            confirmation_token="forged-not-a-real-token",
        )
        forged = "executed"
    except ValueError as exc:
        forged = str(exc)
    forged_ok = bool(forged) and forged != "executed" and (
        "awaiting_confirm" in forged.lower() or "No awaiting" in forged
    )
    evidence["cases"]["forged_token_rejected"] = {
        "status": "PASS" if forged_ok else "FAIL",
        "detail": forged,
    }

    if not token:
        evidence["finishedAt"] = utcnow()
        OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        return 1

    # --- Case 3: confirm turn with server token → real write + Module A ---
    result = execute_extension_action(
        ctx,
        org_id=ORG,
        user_id=ACTOR,
        action=None,
        params={"name": "ATTACKER_OVERRIDE_SHOULD_BE_IGNORED"},
        page_url=page_url,
        confirmation_token=token,
    )
    run_id = result.get("runId")
    evidence["cases"]["confirm_and_write"] = {
        "status": "PASS" if result.get("success") and run_id else "PARTIAL" if run_id else "FAIL",
        "success": result.get("success"),
        "invokeAction": result.get("invokeAction"),
        "runId": run_id,
        "outcomeUrl": result.get("outcomeUrl"),
        "businessOutcomeUrl": result.get("businessOutcomeUrl"),
        "source": result.get("source"),
        "error": result.get("error"),
        "dataKeys": sorted(list((result.get("data") or {}).keys()))[:20],
    }

    # --- Case 4: Outcomes / run row shape (same surface as chat) ---
    outcome_pass = False
    outcome_row = None
    run_row = None
    if run_id:
        runs = (
            client.table("workflow_runs")
            .select("id, status, parameters, definition_snapshot")
            .eq("id", run_id)
            .eq("org_id", ORG)
            .limit(1)
            .execute()
        ).data or []
        run_row = runs[0] if runs else None
        # Business outcomes list is derived from runs / Module A — check contract runs too
        try:
            contract = (
                client.table("runs")
                .select("id, status, metadata, source")
                .eq("id", run_id)
                .limit(1)
                .execute()
            ).data or []
        except Exception:
            contract = []
        if not contract:
            try:
                contract = (
                    client.table("runs")
                    .select("id, status")
                    .eq("org_id", ORG)
                    .limit(1)
                    .execute()
                ).data or []
            except Exception:
                contract = []

        params = (run_row or {}).get("parameters") or {}
        snap = (run_row or {}).get("definition_snapshot") or {}
        source_ok = params.get("source") == "browser_extension" and snap.get("source") == "browser_extension"

        from app.routers.business_outcomes import _project_from_run

        dto = None
        dto_error = None
        try:
            dto = _project_from_run(client, ORG, run_id, "production")
        except Exception as exc:  # noqa: BLE001
            dto_error = str(exc)[:400]

        audits = (
            client.table("audit_events")
            .select("action, created_at")
            .eq("org_id", ORG)
            .eq("resource_id", run_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        ).data or []

        dto_source = (dto or {}).get("source") if isinstance(dto, dict) else None
        outcome_pass = (
            bool(run_row)
            and source_ok
            and bool(result.get("success"))
            and bool(dto)
            and dto_source == "browser_extension"
        )
        evidence["cases"]["outcomes_entry"] = {
            "status": "PASS" if outcome_pass else "FAIL",
            "runId": run_id,
            "workflowRunStatus": (run_row or {}).get("status"),
            "parametersSource": params.get("source"),
            "definitionSource": snap.get("source"),
            "moduleASource": result.get("source"),
            "businessOutcomeDto": {
                "id": (dto or {}).get("id"),
                "runId": (dto or {}).get("runId"),
                "status": (dto or {}).get("status"),
                "source": dto_source,
                "lifecycleState": (dto or {}).get("lifecycleState"),
            }
            if dto
            else None,
            "dtoError": dto_error,
            "auditActions": [a.get("action") for a in audits],
            "openUrl": f"https://gravitre.app/outcomes/{run_id}",
            "sameShapeNote": (
                "Projected via _project_from_run — identical DTO path as GET /api/business-outcomes"
            ),
        }
    else:
        evidence["cases"]["outcomes_entry"] = {"status": "FAIL", "detail": "no runId"}

    # Replay token must fail
    replay = None
    try:
        execute_extension_action(
            ctx,
            org_id=ORG,
            user_id=ACTOR,
            action=None,
            params={},
            page_url=page_url,
            confirmation_token=token,
        )
        replay = "executed"
    except ValueError as exc:
        replay = str(exc)
    evidence["cases"]["token_replay_rejected"] = {
        "status": "PASS" if replay and replay != "executed" else "FAIL",
        "detail": replay,
    }

    # Notification fanout: durable row with UUID entity_id (run_id), not HubSpot list_id
    if run_id:
        notifs = (
            client.table("notifications")
            .select("id, type, entity_id, entity_type, url, created_at")
            .eq("org_id", ORG)
            .eq("user_id", ACTOR)
            .eq("entity_id", run_id)
            .eq("type", "run_completed")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ).data or []
        n = notifs[0] if notifs else None
        evidence["cases"]["notification_fanout"] = {
            "status": "PASS" if n and str(n.get("entity_id")) == run_id else "FAIL",
            "notificationId": (n or {}).get("id"),
            "entityId": (n or {}).get("entity_id"),
            "entityType": (n or {}).get("entity_type"),
            "url": (n or {}).get("url"),
            "note": "entity_id must be run UUID — never HubSpot list_id int string",
        }
    else:
        evidence["cases"]["notification_fanout"] = {
            "status": "FAIL",
            "detail": "no runId",
        }

    evidence["finishedAt"] = utcnow()
    statuses = [c.get("status") for c in evidence["cases"].values()]
    evidence["overall"] = (
        "PASS" if statuses and all(s == "PASS" for s in statuses) else "PARTIAL"
        if any(s == "PASS" for s in statuses)
        else "FAIL"
    )
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
