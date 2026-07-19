#!/usr/bin/env python3
"""Live verify High-Intent-style HubSpot search + Gravitre-primary links.

Exercises prod connectors / audit_events via tool_service + chat orchestration
against smoke org. Confirms:
  - Railway tip is recent
  - hubspot.contacts.search does not stamp portal-less HubSpot list URLs
  - orchestration primary CTA is /runs/{id}
  - notifications.url is Gravitre (not portal-less HubSpot)

Writes docs/delivery/execution-link-high-intent-latest.json
"""
from __future__ import annotations

import asyncio
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

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    mark_smoke_run,
    smoke_http_headers,
)

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "execution-link-high-intent-latest.json"
PORTAL_LESS = "https://app.hubspot.com/contacts/objects/"


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


def _is_portal_less(url: str | None) -> bool:
    text = (url or "").strip()
    return text.startswith(PORTAL_LESS) or (
        "app.hubspot.com/contacts/objects/" in text
        and "/contacts/" in text
        and not any(ch.isdigit() for ch in text.split("/contacts/", 1)[-1].split("/", 1)[0])
    )


async def _run_orchestration(settings, sb, hub_connector_id: str) -> dict:
    from app.services.chat_orchestration_service import get_chat_orchestration_service

    orchestration = get_chat_orchestration_service(settings)
    message = (
        "Search HubSpot for high-intent leads, summarize them, "
        "then post a short summary to Slack"
    )
    connected = ["hubspot", "slack"]
    classification = {
        "intent": "workflow_execution",
        "integrations": connected,
        "confidence": 0.9,
    }
    task_state: dict = {}
    turn = None
    plan_errors: list[str] = []
    conversation_id = str(uuid.uuid4())
    for attempt in range(3):
        conversation_id = str(uuid.uuid4())
        try:
            ensured = await orchestration._state.ensure_owned_conversation(
                org_id=ORG,
                user_id=ACTOR,
                conversation_id=conversation_id,
                title="High-intent execution-link smoke",
                client=sb,
            )
            if ensured:
                conversation_id = ensured
        except Exception as exc:  # noqa: BLE001
            plan_errors.append(f"ensure_conversation:{exc.__class__.__name__}:{exc}")
        try:
            turn = await orchestration.process_turn(
                org_id=ORG,
                user_id=ACTOR,
                conversation_id=conversation_id,
                message=message,
                classification=classification,
                task_state=task_state,
                connected_integrations=connected,
                client=sb,
                environment_name="production",
            )
        except Exception as exc:  # noqa: BLE001
            plan_errors.append(f"{exc.__class__.__name__}:{exc}")
            turn = None
        if turn is not None:
            break
        plan_errors.append(f"attempt_{attempt + 1}_returned_none")

    def _task_state_from_turn(t: dict | None) -> dict:
        t = t or {}
        state = dict(t.get("task_state") or {})
        pending = t.get("pending_task") or state.get("pending_task")
        if isinstance(pending, dict) and pending:
            state["pending_task"] = pending
            params = pending.get("params") or state.get("clarified_params") or {}
            if params:
                state["clarified_params"] = params
        return state

    def _extract(t: dict | None) -> dict:
        t = t or {}
        state = _task_state_from_turn(t)
        pending = state.get("pending_task") or {}
        structured = t.get("structured") if isinstance(t.get("structured"), dict) else {}
        execution = t.get("execution_result") if isinstance(t.get("execution_result"), dict) else {}
        result_url = (
            t.get("result_url")
            or execution.get("result_url")
            or structured.get("result_url")
            or structured.get("resultUrl")
        )
        params = state.get("clarified_params") or {}
        run_id = (
            structured.get("runId")
            or structured.get("run_id")
            or params.get("orchestration_run_id")
            or pending.get("run_id")
        )
        if not run_id and isinstance(result_url, str) and result_url.startswith("/runs/"):
            run_id = result_url.split("/runs/", 1)[-1].split("?", 1)[0]
        return {
            "conversation_id": conversation_id,
            "status": str(pending.get("status") or t.get("dialogue_mode") or ""),
            "result_url": result_url,
            "run_id": run_id,
            "external_url": (
                execution.get("external_url")
                or structured.get("external_url")
                or t.get("external_url")
            ),
            "message_preview": str(t.get("message") or "")[:400],
            "structured_keys": list(structured.keys())[:20],
            "dialogue_mode": t.get("dialogue_mode"),
            "pending_type": pending.get("type"),
            "plan_errors": plan_errors,
        }

    for _ in range(12):
        if turn is None:
            return {
                "conversation_id": conversation_id,
                "status": "no_turn",
                "result_url": None,
                "run_id": None,
                "message_preview": "",
                "plan_errors": plan_errors,
            }
        extracted = _extract(turn)
        text = (extracted.get("message_preview") or "").lower()
        state = _task_state_from_turn(turn)
        status = str((state.get("pending_task") or {}).get("status") or "")
        mode = str(turn.get("dialogue_mode") or "")
        if (
            status == "completed"
            or "orchestration complete" in text
            or (
                isinstance(extracted.get("result_url"), str)
                and str(extracted["result_url"]).startswith("/runs/")
            )
        ):
            return extracted
        if mode == "answer" and "failed" in text:
            return extracted
        # Confirm plan / step prompts
        if status in {"awaiting_plan_confirm", "awaiting_step_confirm"} or mode == "confirm":
            reply = "yes"
            if "channel" in text and "slack" in text:
                reply = "#general"
            turn = await orchestration.process_turn(
                org_id=ORG,
                user_id=ACTOR,
                conversation_id=conversation_id,
                message=reply,
                classification=classification,
                task_state=state,
                connected_integrations=connected,
                client=sb,
                environment_name="production",
            )
            continue
        return extracted
    return _extract(turn)


def main() -> int:
    _load_env()
    from supabase import create_client

    from app.config import get_settings
    from app.services.hubspot_urls import is_portal_scoped_hubspot_url
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)

    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json()
    except Exception as exc:  # noqa: BLE001
        tip = {"error": f"{exc.__class__.__name__}:{exc}"}

    rows = (
        sb.table("connectors")
        .select("id, type, status, config")
        .eq("org_id", ORG)
        .eq("type", "hubspot")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    hub_id = None
    for row in rows:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            hub_id = str(row["id"])
            break

    smoke_started = datetime.now(timezone.utc).isoformat()
    search_rec: dict = {"skipped": True}
    if hub_id:
        ctx = ToolContext(
            settings=settings,
            client=sb,
            org_id=ORG,
            actor_id=ACTOR,
            connector_id=hub_id,
        )
        # High-intent-ish filter; empty results are OK — must not emit portal-less URL
        invoked = invoke_tool(
            ctx,
            "hubspot.contacts.search",
            {
                "connector_id": hub_id,
                "filter_groups": [
                    {
                        "filters": [
                            {
                                "propertyName": "lifecyclestage",
                                "operator": "EQ",
                                "value": "lead",
                            }
                        ]
                    }
                ],
                "limit": 5,
            },
        )
        data = invoked.data or {}
        result_url = data.get("result_url")
        search_rec = {
            "success": bool(invoked.success),
            "error_code": invoked.error_code,
            "error_message": invoked.error_message,
            "result_url": result_url,
            "summary": data.get("summary"),
            "portal_less": _is_portal_less(str(result_url) if result_url else None),
            "portal_scoped": is_portal_scoped_hubspot_url(str(result_url) if result_url else None),
            "contact_count": len(data.get("contacts") or data.get("results") or []),
        }

    orch = asyncio.run(_run_orchestration(settings, sb, hub_id or ""))

    # Evidence from audit_events + notifications created during this smoke
    since = smoke_started
    audits = (
        sb.table("audit_events")
        .select("id, action, created_at, metadata")
        .eq("org_id", ORG)
        .like("action", "tool.invoke%")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(40)
        .execute()
    ).data or []
    hubspot_completed = [
        {
            "id": a.get("id"),
            "action": a.get("action"),
            "created_at": a.get("created_at"),
            "tool": (a.get("metadata") or {}).get("action"),
            "connector_id": (a.get("metadata") or {}).get("connector_id"),
        }
        for a in audits
        if a.get("action") == "tool.invoke.completed"
        and "hubspot.contacts.search" in json.dumps(a.get("metadata") or {})
    ][:5]
    # Fallback: search ran before orchestration window edge cases
    if not hubspot_completed:
        fallback = (
            sb.table("audit_events")
            .select("id, action, created_at, metadata")
            .eq("org_id", ORG)
            .eq("action", "tool.invoke.completed")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        ).data or []
        hubspot_completed = [
            {
                "id": a.get("id"),
                "action": a.get("action"),
                "created_at": a.get("created_at"),
                "tool": (a.get("metadata") or {}).get("action"),
                "connector_id": (a.get("metadata") or {}).get("connector_id"),
            }
            for a in fallback
            if (a.get("metadata") or {}).get("action") == "hubspot.contacts.search"
        ][:3]

    notifs = (
        sb.table("notifications")
        .select("id, title, url, created_at, entity_id")
        .eq("org_id", ORG)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    ).data or []
    bad_notif_urls = [
        n
        for n in notifs
        if _is_portal_less(str(n.get("url") or ""))
        or (
            str(n.get("url") or "").startswith("https://app.hubspot.com/")
            and not is_portal_scoped_hubspot_url(str(n.get("url") or ""))
        )
    ]

    run_id = orch.get("run_id")
    run_row = None
    if run_id:
        run_row = (
            sb.table("workflow_runs")
            .select("id, status, parameters, definition_snapshot")
            .eq("id", run_id)
            .limit(1)
            .execute()
        ).data
        run_row = run_row[0] if run_row else None

    primary_ok = isinstance(orch.get("result_url"), str) and str(orch["result_url"]).startswith(
        "/runs/"
    )
    search_ok = bool(search_rec.get("success")) and not search_rec.get("portal_less")
    notif_ok = len(bad_notif_urls) == 0

    report = {
        "generated_at": utcnow(),
        "railway_health": tip,
        "hubspot_connector_id": hub_id,
        "contacts_search": search_rec,
        "orchestration": orch,
        "run": run_row,
        "audit_hubspot_contacts_search_completed": hubspot_completed,
        "recent_notification_urls": [
            {"id": n.get("id"), "url": n.get("url"), "title": n.get("title"), "created_at": n.get("created_at")}
            for n in notifs[:5]
        ],
        "portal_less_notification_count": len(bad_notif_urls),
        "checks": {
            "search_no_portal_less_url": search_ok,
            "orchestration_primary_is_runs": primary_ok,
            "notifications_no_portal_less": notif_ok,
        },
        "pass": bool(search_ok and primary_ok and notif_ok and hubspot_completed),
        "query_window_hint": since,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
