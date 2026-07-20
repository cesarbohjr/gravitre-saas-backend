#!/usr/bin/env python3
"""Wave67 prod SSE diagnostic — three turns, full event dump."""
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

import httpx
import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    mark_smoke_run,
    smoke_http_headers,
)

ORG = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
BASE = "https://gravitre-saas-backend-production.up.railway.app"
OUT = REPO / "docs" / "delivery" / "wave67-prod-sse-diag.json"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    secret = env["SUPABASE_JWT_SECRET"]
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in re.split(r"\n\n+", raw):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        data_lines = [ln[5:].lstrip() for ln in lines if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            events.append({"_raw": payload[:300]})
    return events


def _event_type(ev: dict[str, Any]) -> str:
    return str(ev.get("type") or ev.get("sse_type") or "")


def _is_tool_related(et: str) -> bool:
    et_l = et.lower()
    return any(
        x in et_l
        for x in (
            "tool-input",
            "tool-output",
            "tool-call",
            "tool-result",
            "tool-error",
            "tool_invoke",
        )
    )


def _print_and_summarize(label: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    text_preview_parts: list[str] = []
    printed: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {
        "error_codes": [],
        "pending_plans": [],
        "msp_prospects_mentions": [],
        "result_urls": [],
        "assumption_notes": [],
        "dialogue_modes": [],
        "tool_names": [],
        "execution_success": [],
    }

    print(f"\n{'=' * 72}\nTURN {label} — {len(events)} events\n{'=' * 72}")
    for idx, ev in enumerate(events):
        et = _event_type(ev)
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        row: dict[str, Any] = {"i": idx, "type": et}
        print(f"\n[{idx}] type={et!r}")

        if _is_tool_related(et):
            keys = sorted(data.keys()) if data else sorted(
                k for k in ev.keys() if k not in ("type", "sse_type")
            )
            payload = data if data else {k: ev[k] for k in keys if k in ev}
            trunc = json.dumps(payload, default=str)[:800]
            print(f"  tool data keys: {keys}")
            print(f"  data[:800]: {trunc}")
            row["data_keys"] = keys
            row["data_trunc"] = trunc
            tn = data.get("toolName") or data.get("tool_name") or ev.get("toolName")
            if tn:
                evidence["tool_names"].append(tn)
            out = data.get("output") if isinstance(data.get("output"), dict) else data
            if isinstance(out, dict):
                ec = out.get("errorCode") or out.get("error_code")
                if ec:
                    evidence["error_codes"].append({"i": idx, "tool": tn, "code": ec})
                if "success" in out:
                    evidence["execution_success"].append(
                        {"i": idx, "tool": tn, "success": out.get("success")}
                    )

        if et in {"data-intelligence", "intelligence-metadata", "data-assistant-metadata"}:
            dialogue = data.get("dialogueMode") or data.get("dialogue_mode")
            expl = data.get("answerExplanation") or data.get("answer_explanation") or ""
            pending = data.get("pendingTask") or data.get("pending_task")
            exec_res = data.get("executionResult") or data.get("execution_result")
            expl_s = str(expl)[:200]
            print(f"  dialogueMode: {dialogue!r}")
            print(f"  answerExplanation[:200]: {expl_s!r}")
            row["dialogueMode"] = dialogue
            row["answerExplanation_200"] = expl_s
            if dialogue:
                evidence["dialogue_modes"].append(dialogue)
            if pending is not None:
                pkeys = sorted(pending.keys()) if isinstance(pending, dict) else [type(pending).__name__]
                print(f"  pendingTask keys: {pkeys}")
                row["pendingTask_keys"] = pkeys
                evidence["pending_plans"].append(
                    {
                        "i": idx,
                        "keys": pkeys,
                        "preview": json.dumps(pending, default=str)[:400],
                    }
                )
            else:
                print("  pendingTask: None")
            if isinstance(exec_res, dict):
                ekeys = sorted(exec_res.keys())
                notes = exec_res.get("assumption_notes") or exec_res.get("assumptionNotes")
                rurl = exec_res.get("result_url") or exec_res.get("resultUrl")
                print(f"  executionResult keys: {ekeys}")
                print(f"  assumption_notes: {notes!r}")
                print(f"  result_url: {rurl!r}")
                row["executionResult_keys"] = ekeys
                row["assumption_notes"] = notes
                row["result_url"] = rurl
                if notes:
                    evidence["assumption_notes"].append({"i": idx, "notes": notes})
                if rurl:
                    evidence["result_urls"].append({"i": idx, "url": rurl})
                ec = exec_res.get("error_code") or exec_res.get("errorCode")
                if ec:
                    evidence["error_codes"].append({"i": idx, "source": "executionResult", "code": ec})
            else:
                print(f"  executionResult: {type(exec_res).__name__}={exec_res!r}"[:200])

            blob = json.dumps(data, default=str)
            if "MSP Prospects" in blob or "msp prospects" in blob.lower():
                evidence["msp_prospects_mentions"].append({"i": idx, "snippet": blob[:300]})

        if et in {"text-delta", "text-start"}:
            delta = data.get("delta") or data.get("text") or ev.get("delta") or ev.get("text") or ""
            if delta:
                text_preview_parts.append(str(delta))

        # also scan whole event for MSP / result_url / assumption
        blob_all = json.dumps(ev, default=str)
        if "MSP Prospects" in blob_all and not any(
            m.get("i") == idx for m in evidence["msp_prospects_mentions"]
        ):
            evidence["msp_prospects_mentions"].append({"i": idx, "snippet": blob_all[:300]})

        printed.append(row)

    preview = "".join(text_preview_parts)
    print(f"\n--- text preview ({len(preview)} chars) ---\n{preview[:1200]}")
    return {
        "printed": printed,
        "text_preview": preview,
        "evidence": evidence,
        "events": events,
    }


async def _chat(
    client: httpx.AsyncClient,
    *,
    token: str,
    text: str,
    conversation_id: str,
    tools: list[str],
) -> tuple[int, str, list[dict[str, Any]]]:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": ORG,
        "conversation_id": conversation_id,
        "tools": tools,
        "mode": "reasoning",
    }
    r = await client.post(
        f"{BASE}/api/assistant/chat",
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": ORG,
            "X-Environment": "production",
            "Accept": "text/event-stream",
        },
        timeout=180.0,
    )
    raw = r.text
    return r.status_code, raw, _parse_sse(raw)


async def main() -> None:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.workflows.repository import get_supabase_client
    from app.config import get_settings

    settings = get_settings()
    sb = get_supabase_client(settings)
    actor = (env.get("OAUTH_SMOKE_USER_ID") or "").strip()
    if not actor:
        rows = sb.table("organization_members").select("user_id").eq("org_id", ORG).limit(1).execute()
        actor = str((rows.data or [{}])[0].get("user_id") or "")
    users = sb.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    token = _mint_token(env, actor, email)

    turns = [
        {
            "id": "A_slack_fail",
            "text": "Post a Slack message to #general saying wave67-prod-diag — ignore",
            "tools": ["slack_post_message", "connector_status"],
        },
        {
            "id": "B_apollo_named",
            "text": "Create an Apollo contact list named exactly 'gravitre-wave67-prod-diag-20260711'",
            "tools": ["apollo_lists_create", "apollo_lists_list"],
        },
        {
            "id": "C_apollo_omit_name",
            "text": "In Apollo, create a contact list.",
            "tools": ["apollo_lists_create", "apollo_lists_list"],
        },
    ]

    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "org_id": ORG,
        "actor_id": actor,
        "base_url": BASE,
        "turns": {},
    }

    async with httpx.AsyncClient() as client:
        for t in turns:
            conv = str(uuid.uuid4())
            print(f"\n>>> Starting {t['id']} conv={conv}")
            status, raw, events = await _chat(
                client,
                token=token,
                text=t["text"],
                conversation_id=conv,
                tools=t["tools"],
            )
            summary = _print_and_summarize(t["id"], events)
            report["turns"][t["id"]] = {
                "conversation_id": conv,
                "prompt": t["text"],
                "tools": t["tools"],
                "http_status": status,
                "raw_sse_chars": len(raw),
                "event_count": len(events),
                "text_preview": summary["text_preview"],
                "evidence": summary["evidence"],
                "printed": summary["printed"],
                "events": summary["events"],
            }

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n\nWrote {OUT}")

    # Concise claim evidence rollup
    print("\n" + "=" * 72)
    print("EVIDENCE ROLLUP (claims 2/3/4)")
    print("=" * 72)
    for tid, td in report["turns"].items():
        ev = td["evidence"]
        print(f"\n{tid}:")
        print(f"  error_codes: {ev['error_codes']}")
        print(f"  pending_plans: {len(ev['pending_plans'])} — {[p.get('keys') for p in ev['pending_plans'][:3]]}")
        print(f"  msp_prospects: {ev['msp_prospects_mentions']}")
        print(f"  result_urls: {ev['result_urls']}")
        print(f"  assumption_notes: {ev['assumption_notes']}")
        print(f"  dialogue_modes: {ev['dialogue_modes']}")
        print(f"  tools: {ev['tool_names']}")


if __name__ == "__main__":
    asyncio.run(main())
