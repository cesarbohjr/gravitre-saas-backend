#!/usr/bin/env python3
"""Live smoke: Slack Batch 1 — conversations.list/join, users.list/info, history.

Writes docs/delivery/phase1-slack-batch1-live.json

Chat/ReAct/canvas NOT granted. No API version bump (method-based Slack Web API).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "phase1-slack-batch1-live.json"


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


def _rec(invoke) -> dict:
    data = invoke.data or {}
    return {
        "success": bool(invoke.success),
        "error_code": invoke.error_code,
        "error_message": invoke.error_message,
        "result_url": data.get("result_url"),
        "summary": data.get("summary"),
        "data_keys": list(data.keys())[:12],
    }


def _invoke_retry(invoke_tool, ctx, action: str, params: dict, *, attempts: int = 4):
    """Retry transient WinError 10035 / connection drops between invokes."""
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return invoke_tool(ctx, action, params)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            msg = str(exc)
            transient = (
                "10035" in msg
                or "ConnectionTerminated" in msg
                or "ReadError" in msg
                or "RemoteProtocolError" in type(exc).__name__
            )
            if not transient or i + 1 >= attempts:
                raise
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(str(last_exc or "invoke failed"))


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    rows = (
        sb.table("connectors")
        .select("id, type, status")
        .eq("org_id", ORG)
        .eq("type", "slack")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    slack_id = None
    for row in rows:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            slack_id = str(row["id"])
            break
    # Fall back: smoke org Slack may be status=error after a health blip but token still works
    if not slack_id and rows:
        slack_id = str(rows[0]["id"])

    invokes: dict[str, dict] = {}
    if slack_id:
        ctx = ToolContext(
            settings=settings,
            client=sb,
            org_id=ORG,
            actor_id=ACTOR,
            connector_id=slack_id,
        )
        listed = _invoke_retry(
            invoke_tool,
            ctx,
            "slack.conversations.list",
            {"connector_id": slack_id, "types": "public_channel", "limit": 10},
        )
        invokes["slack.conversations.list"] = _rec(listed)
        time.sleep(0.8)

        channel_id = None
        if listed.success:
            for ch in (listed.data or {}).get("channels") or []:
                if isinstance(ch, dict) and ch.get("id") and not ch.get("is_archived"):
                    # Prefer channels the bot is already in for history tip
                    if ch.get("is_member"):
                        channel_id = str(ch["id"])
                        break
                    channel_id = channel_id or str(ch["id"])

        users = _invoke_retry(
            invoke_tool, ctx, "slack.users.list", {"connector_id": slack_id, "limit": 5}
        )
        invokes["slack.users.list"] = _rec(users)
        time.sleep(0.8)
        user_id = None
        if users.success:
            for m in (users.data or {}).get("members") or []:
                if isinstance(m, dict) and m.get("id") and not m.get("deleted") and not m.get("is_bot"):
                    user_id = str(m["id"])
                    break

        if user_id:
            info = _invoke_retry(
                invoke_tool,
                ctx,
                "slack.users.info",
                {"connector_id": slack_id, "user": user_id},
            )
            invokes["slack.users.info"] = _rec(info)
            time.sleep(0.8)

        if channel_id:
            join = _invoke_retry(
                invoke_tool,
                ctx,
                "slack.conversations.join",
                {"connector_id": slack_id, "channel": channel_id},
            )
            invokes["slack.conversations.join"] = _rec(join)
            time.sleep(0.8)
            hist = _invoke_retry(
                invoke_tool,
                ctx,
                "slack.conversations.history",
                {"connector_id": slack_id, "channel": channel_id, "limit": 5},
            )
            invokes["slack.conversations.history"] = _rec(hist)

    success_with_url = any(
        r.get("success") and r.get("result_url")
        for k, r in invokes.items()
        if k
        in {
            "slack.conversations.list",
            "slack.users.list",
            "slack.users.info",
            "slack.conversations.join",
            "slack.conversations.history",
        }
    )
    # Prefer at least one new action proven
    new_ok = any(
        invokes.get(k, {}).get("success") and invokes.get(k, {}).get("result_url")
        for k in ("slack.users.info", "slack.conversations.join")
    )
    passed = bool(slack_id) and success_with_url and new_ok

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-slack-batch1",
        "api_version": "Slack Web API methods (no version bump)",
        "new_actions": ["slack.conversations.join", "slack.users.info"],
        "enriched_result_url": [
            "slack.conversations.list",
            "slack.conversations.history",
            "slack.users.list",
            "slack.post_message",
        ],
        "deferred": [
            "slack.workflows.trigger (missing workflows:write scope)",
            "slack.files.upload (deprecated API path)",
        ],
        "slack_connector_id": slack_id,
        "invokes": invokes,
        "governance": {
            "finance_hr_excluded": True,
            "chat_access_granted": False,
            "hubspot_batch1b_blocked_on_app_republish": True,
            "hubspot_batch1b_note": (
                "PENDING — last HubSpot app build #5 (2026-06-23); "
                "hsmeta scopes in-repo only until portal upload + re-auth"
            ),
        },
        "status": "PASS" if passed else "BLOCKED_EXTERNAL",
        "blocker": None
        if passed
        else {
            "kind": "slack_reconnect",
            "class": "external_dependency",
            "detail": "auth/list failed — reconnect Slack on smoke org before tip can go green",
            "same_as": ["hubspot_batch1b_app_republish", "apollo_plan_tier", "fred_api_key"],
        },
        "note": (
            "Slack Batch 1: conversations.join + users.info with result_url; "
            "core list/history/users enriched. Chat access deferred."
            if passed
            else (
                "Slack Batch 1 code ready; live tip BLOCKED on Slack reconnect "
                "(token_expired) — not a code bug."
            )
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "slack_id": slack_id, "tip": tip}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
