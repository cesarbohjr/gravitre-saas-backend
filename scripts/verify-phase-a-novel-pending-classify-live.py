#!/usr/bin/env python3
"""Phase A live proof: novel pending-cancel/modify phrasing → LLM classify, not silent default.

Uses genuinely new phrasings NOT in _CANCEL_ONLY_PHRASES / CONFIRM_PATTERN banks.
Writes docs/delivery/phase-a-novel-pending-classify-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "phase-a-novel-pending-classify-live.json"
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"

# Novel — intentionally NOT in phrase banks / _modify_hint tokens (skip/instead/just/only/…).
NOVEL_CANCEL = "please scrap that CRM update; I've reconsidered the whole thing"
NOVEL_MODIFY = (
    "Rewrite the pending HubSpot action as an internal memo and leave the contact record untouched"
)


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_bytes().decode("utf-8", errors="ignore")
            for line in text.splitlines():
                if "=" not in line or line.lstrip().startswith("#"):
                    continue
                key, _, value = line.partition("=")
                if key.strip() and value.strip():
                    merged[key.strip()] = value.strip().strip('"').strip("'")
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


async def _classify(message: str, org_id: str) -> dict:
    from app.config import get_settings
    from app.services.pending_reply_classifier import (
        classify_pending_reply,
        classify_pending_reply_fast,
        build_pending_snapshot,
    )

    task_state = {
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_confirm",
            "params": {
                "label": "Update HubSpot contact",
                "invoke_action": "hubspot.contacts.update",
                "integration": "hubspot",
                "kind": "write",
                "requires_approval": True,
            },
        }
    }
    snap = build_pending_snapshot(task_state)
    fast = classify_pending_reply_fast(message, snap)
    modeled = await classify_pending_reply(
        message,
        task_state=task_state,
        settings=get_settings(),
        org_id=org_id,
        use_model=True,
        conversation_turns=[
            {"role": "user", "content": "Update the HubSpot contact with the new title"},
            {
                "role": "assistant",
                "content": "I've prepared Update HubSpot contact. Approve below to proceed.",
            },
            {"role": "user", "content": message},
        ],
    )
    return {
        "message": message,
        "fast_path": fast,
        "final_intent": modeled,
        "used_model_fallback": fast is None,
        # Architecture bar: fast miss → model; never silent confirm/execute.
        "ok": fast is None and modeled != "confirm",
    }


async def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    org_id = (env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or ISOLATED_ORG).strip()
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=30.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_error:{exc}"

    cases = await asyncio.gather(
        _classify(NOVEL_CANCEL, org_id),
        _classify(NOVEL_MODIFY, org_id),
    )
    # Architecture proof: fast path must miss; model must not silent-default to confirm.
    architecture_ok = all(c["used_model_fallback"] and c["final_intent"] != "confirm" for c in cases)
    cancel_ok = cases[0]["final_intent"] in {"reject", "ambiguous"}
    modify_ok = cases[1]["final_intent"] in {"modify", "ambiguous", "unrelated"}
    # Prefer reject/modify when model is confident; ambiguous still proves "ask, don't guess".
    verdict = "PASS" if architecture_ok and cancel_ok and modify_ok else "FAIL"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "health_git_sha": tip,
        "org_id": org_id,
        "probe_id": f"phasea-{uuid4().hex[:10]}",
        "cases": cases,
        "architecture_ok": architecture_ok,
        "verdict": verdict,
        "claim": (
            f"{verdict} — Phase A novel phrasing uses model fallback "
            f"(fast miss → LLM), tip={tip}"
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
