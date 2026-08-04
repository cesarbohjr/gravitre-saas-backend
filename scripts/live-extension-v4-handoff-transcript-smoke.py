#!/usr/bin/env python3
"""v4 live proof: overlay page-context Q + write handoff, same conversation transcript both sides."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "browser-extension-v4-handoff-transcript-live.json"
PAGE_URL = "https://www.linkedin.com/in/extension-v4-handoff-transcript"
PAGE_CONTEXT = {
    "fullName": "Casey Operator",
    "firstName": "Casey",
    "lastName": "Operator",
    "company": "Gravitree Smoke Co",
    "title": "Head of Revenue Ops",
    "email": "casey.operator@example.com",
    "source": "linkedin",
}


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


def _load_messages(client, conversation_id: str) -> list[dict]:
    # conversation_messages rows are scoped by conversation_id (no org_id column).
    rows = (
        client.table("conversation_messages")
        .select("id, role, content, created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
        .data
        or []
    )
    return list(rows)


async def _run() -> dict:
    import app.main  # noqa: F401
    from supabase import create_client

    from app.config import get_settings
    from app.services.extension_bridge_service import chat_from_extension

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    evidence: dict = {"startedAt": utcnow(), "orgId": ORG, "cases": {}}

    quick_msg = (
        "Using only the overlay page context, answer in one sentence: "
        "what is this person's full name, title, and company?"
    )
    quick = await chat_from_extension(
        settings=settings,
        org_id=ORG,
        user_id=ACTOR,
        message=quick_msg,
        page_url=PAGE_URL,
        page_context=PAGE_CONTEXT,
        environment_name="production",
    )
    answer = (quick.get("answer") or "").lower()
    uses_context = ("casey" in answer) or ("gravitree smoke" in answer) or ("revenue" in answer)
    conv_id = str(quick.get("conversationId") or "")
    evidence["cases"]["overlay_quick"] = {
        "status": "PASS"
        if quick.get("success") and uses_context and conv_id and not quick.get("needsHandoff")
        else "FAIL",
        "conversationId": conv_id,
        "needsHandoff": quick.get("needsHandoff"),
        "path": quick.get("path"),
        "answerPreview": (quick.get("answer") or "")[:400],
        "openInGravitreeUrl": quick.get("openInGravitreeUrl"),
    }

    handoff_msg = "Create a HubSpot list for Casey Operator from this page."
    handoff = await chat_from_extension(
        settings=settings,
        org_id=ORG,
        user_id=ACTOR,
        message=handoff_msg,
        page_url=PAGE_URL,
        page_context=PAGE_CONTEXT,
        conversation_id=conv_id,
        environment_name="production",
    )
    url = str(handoff.get("openInGravitreeUrl") or "")
    same_id = str(handoff.get("conversationId") or "") == conv_id and bool(conv_id)
    evidence["cases"]["overlay_handoff"] = {
        "status": "PASS"
        if (
            handoff.get("needsHandoff")
            and same_id
            and "/ai?c=" in url
            and conv_id in url
            and handoff.get("path") == "handoff_short_circuit"
        )
        else "FAIL",
        "conversationId": handoff.get("conversationId"),
        "sameConversationAsQuick": same_id,
        "needsHandoff": handoff.get("needsHandoff"),
        "handoffReason": handoff.get("handoffReason"),
        "path": handoff.get("path"),
        "openInGravitreeUrl": url,
        "answerPreview": (handoff.get("answer") or "")[:400],
    }

    messages = _load_messages(client, conv_id) if conv_id else []
    roles = [str(m.get("role") or "") for m in messages]
    blob = "\n".join(str(m.get("content") or "") for m in messages).lower()
    has_quick_user = "full name" in blob and "title" in blob
    has_quick_assistant = ("casey" in blob) or ("gravitree smoke" in blob)
    has_handoff_user = "hubspot list" in blob
    has_handoff_assistant = "same conversation" in blob or "full gravitree chat" in blob
    evidence["cases"]["transcript_both_sides"] = {
        "status": "PASS"
        if (
            len(messages) >= 4
            and roles.count("user") >= 2
            and roles.count("assistant") >= 2
            and has_quick_user
            and has_quick_assistant
            and has_handoff_user
            and has_handoff_assistant
        )
        else "FAIL",
        "messageCount": len(messages),
        "roles": roles,
        "hasQuickUser": has_quick_user,
        "hasQuickAssistant": has_quick_assistant,
        "hasHandoffUser": has_handoff_user,
        "hasHandoffAssistant": has_handoff_assistant,
        "preview": [
            {
                "role": m.get("role"),
                "content": str(m.get("content") or "")[:180],
            }
            for m in messages[:8]
        ],
        "fullAppUrl": f"https://gravitre.app/ai?c={conv_id}" if conv_id else None,
    }

    evidence["finishedAt"] = utcnow()
    evidence["overall"] = (
        "PASS"
        if all(c.get("status") == "PASS" for c in evidence["cases"].values())
        else "FAIL"
    )
    return evidence


def main() -> int:
    _load_env()
    evidence = asyncio.run(_run())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence.get("overall") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
