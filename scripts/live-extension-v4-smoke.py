#!/usr/bin/env python3
"""Live proof: extension v4 overlay chat — page context + handoff via unified-turn."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "browser-extension-v4-live.json"
PAGE_URL = "https://www.linkedin.com/in/extension-v4-smoke-profile"
PAGE_CONTEXT = {
    "fullName": "Casey Operator",
    "firstName": "Casey",
    "lastName": "Operator",
    "company": "Gravitre Smoke Co",
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


async def _run() -> dict:
    import app.main  # noqa: F401 — warm router graph
    from app.config import get_settings
    from app.services.extension_bridge_service import chat_from_extension

    settings = get_settings()
    evidence: dict = {"startedAt": utcnow(), "cases": {}}

    quick = await chat_from_extension(
        settings=settings,
        org_id=ORG,
        user_id=ACTOR,
        message=(
            "Using only the overlay page context, answer in one sentence: "
            "what is this person's full name, title, and company?"
        ),
        page_url=PAGE_URL,
        page_context=PAGE_CONTEXT,
        environment_name="production",
    )
    answer = (quick.get("answer") or "").lower()
    uses_context = ("casey" in answer) or ("gravitre smoke" in answer) or ("revenue" in answer)
    evidence["cases"]["quick_page_context"] = {
        "status": "PASS" if quick.get("success") and uses_context else "FAIL",
        "conversationId": quick.get("conversationId"),
        "needsHandoff": quick.get("needsHandoff"),
        "handoffReason": quick.get("handoffReason"),
        "answerPreview": (quick.get("answer") or "")[:400],
        "openInGravitreUrl": quick.get("openInGravitreUrl"),
        "path": quick.get("path"),
        "usesPageContext": uses_context,
        "acceptedPaths": [
            "execute_task_streaming",
            "execute_task_streaming+page_context_answer",
        ],
    }
    if evidence["cases"]["quick_page_context"]["status"] == "PASS":
        if quick.get("path") not in {
            "execute_task_streaming",
            "execute_task_streaming+page_context_answer",
        }:
            evidence["cases"]["quick_page_context"]["status"] = "FAIL"

    handoff = await chat_from_extension(
        settings=settings,
        org_id=ORG,
        user_id=ACTOR,
        message="Create a HubSpot list for Casey Operator from this page.",
        page_url=PAGE_URL,
        page_context=PAGE_CONTEXT,
        conversation_id=quick.get("conversationId"),
        environment_name="production",
    )
    url = str(handoff.get("openInGravitreUrl") or "")
    evidence["cases"]["handoff"] = {
        "status": "PASS"
        if handoff.get("needsHandoff")
        and "/ai?c=" in url
        and handoff.get("conversationId")
        and handoff.get("path") in {"handoff_short_circuit", "execute_task_streaming"}
        else "FAIL",
        "conversationId": handoff.get("conversationId"),
        "needsHandoff": handoff.get("needsHandoff"),
        "handoffReason": handoff.get("handoffReason"),
        "path": handoff.get("path"),
        "openInGravitreUrl": url,
        "answerPreview": (handoff.get("answer") or "")[:400],
    }

    overall = (
        "PASS"
        if all(c.get("status") == "PASS" for c in evidence["cases"].values())
        else "FAIL"
    )
    evidence["overall"] = overall
    evidence["finishedAt"] = utcnow()
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
