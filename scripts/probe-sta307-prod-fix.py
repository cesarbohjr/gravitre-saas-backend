#!/usr/bin/env python3
"""STA-307 / foundation Item 5 — multi-connector HubSpot+Slack orch live verdict.

Two modes (smoke org is usually CONNECTED):

CONNECTED (default):
  - plan labels include HubSpot and Slack as distinct steps
  - HubSpot must NOT be labeled "(not connected)" when connector is healthy
  - pending_task.type == connector_orchestration
  - status awaiting_plan_confirm (writes gated) is PASS
  - elapsed_ms well under 120s chat proxy ceiling

DISCONNECTED (STA307_EXPECT_DISCONNECTED=1):
  - original STA-307 baseline: both steps blocked / not connected copy
  - pending_task.status == blocked (no awaiting_plan_confirm)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
import sys
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))
from isolated_conversation_org import (
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    mark_smoke_run,
    smoke_http_headers,
)
OUT = ROOT / "docs" / "delivery" / "sta307-prod-verdict.json"
ORG = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
BASE = "https://gravitre-saas-backend-production.up.railway.app"
# Tip at last Item-5 fix ship; override with STA307_ALLOW_ANY_SHA=1
EXPECTED_SHA_PREFIX = "19ac9ba7"
CHAT_TIMEOUT = 180.0
PROMPT = (
    "Search HubSpot for high-intent leads and draft a follow-up in Slack "
    "for approval [STA-307-prod {nonce}]"
)
ALLOW_ANY = os.environ.get("STA307_ALLOW_ANY_SHA", "").strip().lower() in {
    "1",
    "true",
    "yes",
}
EXPECT_DISCONNECTED = os.environ.get("STA307_EXPECT_DISCONNECTED", "").strip().lower() in {
    "1",
    "true",
    "yes",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> None:
    for p in (
        BACKEND / ".env",
        BACKEND / ".env.operator.local",
        ROOT / ".env",
        ROOT / ".env.operator.local",
    ):
        if not p.is_file():
            continue
        for k, v in dotenv_values(p).items():
            if v:
                os.environ.setdefault(k, v)


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    intel: list[dict] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            continue
        t = o.get("type")
        if t == "text-delta":
            texts.append(o.get("delta") or "")
        if t == "data-intelligence":
            d = o.get("data") or {}
            intel.append(
                {
                    "dialogueMode": d.get("dialogueMode"),
                    "expl": (d.get("answerExplanation") or "")[:240],
                    "pending": d.get("pendingTask") or d.get("pending_task"),
                    "executionResult": d.get("executionResult") or d.get("execution_result"),
                }
            )
    return {"text": "".join(texts), "intel": intel}


def last_pending(intel: list[dict]) -> dict | None:
    for item in reversed(intel):
        pend = item.get("pending")
        if isinstance(pend, dict) and pend.get("type"):
            return pend
    return None


def step_labels(pending: dict | None) -> list[str]:
    if not isinstance(pending, dict):
        return []
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    steps = params.get("steps") if isinstance(params.get("steps"), list) else []
    out: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        out.append(str(step.get("label") or step.get("description") or ""))
    return out


def step_integrations(pending: dict | None) -> list[str]:
    """Vendor keys from orchestration steps (labels may be generic action names)."""
    if not isinstance(pending, dict):
        return []
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    steps = params.get("steps") if isinstance(params.get("steps"), list) else []
    out: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        plan = step.get("plan") if isinstance(step.get("plan"), dict) else {}
        integ = (
            plan.get("integration")
            or step.get("integration")
            or plan.get("tool_name")
            or step.get("tool_name")
            or ""
        )
        out.append(str(integ).lower())
    return out


def step_skip_reasons(pending: dict | None) -> list[str | None]:
    if not isinstance(pending, dict):
        return []
    params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
    steps = params.get("steps") if isinstance(params.get("steps"), list) else []
    return [
        (step.get("skip_reason") if isinstance(step, dict) else None) for step in steps
    ]


async def main() -> int:
    load_env()
    sys.path.insert(0, str(BACKEND))
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    actor = os.environ.get("OAUTH_SMOKE_USER_ID") or (
        client.table("organization_members")
        .select("user_id")
        .eq("org_id", ORG)
        .limit(1)
        .execute()
        .data[0]["user_id"]
    )
    email = (client.auth.admin.get_user_by_id(actor).user.email) or f"{actor}@gravitre.local"
    url = os.environ["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    tok = jwt.encode(
        {
            "sub": actor,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Accept": "text/event-stream",
    }

    cid = str(uuid.uuid4())
    nonce = uuid.uuid4().hex[:8]
    prompt = PROMPT.format(nonce=nonce)
    report: dict[str, Any] = {
        "probe": "sta307_prod_fix",
        "ticket": "STA-307",
        "pr": 99,
        "expected_sha_prefix": EXPECTED_SHA_PREFIX,
        "started_at": utcnow(),
        "base_url": BASE,
        "org_id": ORG,
        "actor_id": actor,
        "conversation_id": cid,
        "prompt": prompt,
    }

    async with AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT, verify=False) as ac:
        health = (await ac.get("/health")).json()
        sha = str(health.get("git_sha") or "")
        report["prod_health"] = health
        report["prod_sha"] = sha
        report["prod_sha_ok"] = ALLOW_ANY or sha.startswith(EXPECTED_SHA_PREFIX)
        if not report["prod_sha_ok"]:
            report["verdict"] = "BLOCKED_WRONG_SHA"
            report["finished_at"] = utcnow()
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            print("WROTE", OUT)
            return 1

        body = {
            "messages": [{"role": "user", "parts": [{"type": "text", "text": prompt}]}],
            "org_id": ORG,
            "tools": [],
            "mode": "standard",
            "conversation_id": cid,
            "department": "Marketing",
        }
        t0 = time.perf_counter()
        r = await ac.post("/api/assistant/chat", json=body, headers=hdr, timeout=CHAT_TIMEOUT)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        parsed = parse_sse(r.text)
        sse_pending = last_pending(parsed["intel"])

        state_hdr = {k: v for k, v in hdr.items() if k != "Accept"}
        st = await ac.get(
            f"/api/assistant/conversation/{cid}/state",
            headers=state_hdr,
            timeout=60.0,
        )
        task_state = st.json().get("task_state") if st.status_code == 200 else None
        db_pending = (
            (task_state or {}).get("pending_task") if isinstance(task_state, dict) else None
        )

        pending = db_pending if isinstance(db_pending, dict) else sse_pending
        labels = step_labels(pending)
        labels_l = [x.lower() for x in labels]
        integrations = step_integrations(pending)
        skip_reasons = step_skip_reasons(pending)
        hub_idxs = [
            i
            for i, (lb, integ) in enumerate(zip(labels_l, integrations))
            if "hubspot" in lb or "hubspot" in integ
        ]
        slack_idxs = [
            i
            for i, (lb, integ) in enumerate(zip(labels_l, integrations))
            if "slack" in lb or "slack" in integ
        ]
        status = (pending or {}).get("status") if isinstance(pending, dict) else None
        dialogue = None
        for item in reversed(parsed["intel"]):
            if item.get("dialogueMode"):
                dialogue = item.get("dialogueMode")
                break

        labels_ok = (
            len(hub_idxs) >= 1
            and len(slack_idxs) >= 1
            and hub_idxs[0] != slack_idxs[0]
        )
        # Both steps must not be HubSpot-only duplicates
        if len(integrations) >= 2 and all("hubspot" in x for x in integrations[:2]) and not any(
            "slack" in x for x in integrations[:2]
        ):
            labels_ok = False

        fast_ok = elapsed_ms < 45_000  # well under 120s proxy hang
        text = parsed.get("text") or ""
        hub_labels = [lb for lb in labels if "hubspot" in lb.lower()]
        hubspot_false_not_connected = any(
            "not connected" in lb.lower() for lb in hub_labels
        ) or any(
            i < len(skip_reasons)
            and skip_reasons[i]
            and "not connected" in str(skip_reasons[i]).lower()
            for i in hub_idxs
        )
        orch_ok = (
            isinstance(pending, dict) and pending.get("type") == "connector_orchestration"
        )

        if EXPECT_DISCONNECTED:
            blocked_ok = status == "blocked"
            no_confirm = status != "awaiting_plan_confirm"
            copy_ok = (
                "nothing is runnable" in text.lower()
                or "blocked" in text.lower()
                or "not connected" in text.lower()
            )
            status_ok = blocked_ok and no_confirm
            availability_ok = True  # disconnected baseline expects not-connected labels
            pass_all = (
                r.status_code == 200
                and labels_ok
                and status_ok
                and fast_ok
                and orch_ok
            )
            mode = "disconnected"
        else:
            # Connected smoke org: HubSpot must appear as connected; confirm gate is OK.
            status_ok = status in {"awaiting_plan_confirm", "blocked"}
            copy_ok = True
            availability_ok = labels_ok and not hubspot_false_not_connected
            # Both planned steps should be supported (no skip_reason) when connectors healthy
            steps_supported = all(sr is None for sr in skip_reasons) if skip_reasons else False
            pass_all = (
                r.status_code == 200
                and availability_ok
                and status_ok
                and fast_ok
                and orch_ok
                and steps_supported
            )
            mode = "connected"
            blocked_ok = status == "blocked"
            no_confirm = status != "awaiting_plan_confirm"

        report["mode"] = mode
        report["turn"] = {
            "http": r.status_code,
            "elapsed_ms": elapsed_ms,
            "dialogue_mode": dialogue,
            "text_head": text[:500],
            "intel_count": len(parsed["intel"]),
            "sse_pending_status": (sse_pending or {}).get("status") if sse_pending else None,
            "db_pending_status": (db_pending or {}).get("status") if isinstance(db_pending, dict) else None,
            "pending_type": (pending or {}).get("type") if isinstance(pending, dict) else None,
            "pending_status": status,
            "labels": labels,
            "integrations": integrations,
            "skip_reasons": skip_reasons,
            "state_http": st.status_code,
        }
        report["checks"] = {
            "mode": mode,
            "labels_hubspot_and_slack": labels_ok,
            "hubspot_not_falsely_disconnected": not hubspot_false_not_connected,
            "steps_supported": all(sr is None for sr in skip_reasons) if skip_reasons else False,
            "status_ok": status_ok,
            "status_blocked": blocked_ok,
            "not_awaiting_confirm": no_confirm,
            "elapsed_under_45s": fast_ok,
            "honest_copy": copy_ok,
            "orch_type": orch_ok,
        }
        report["verdict"] = "PASS" if pass_all else "FAIL"
        report["finished_at"] = utcnow()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("WROTE", OUT)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
