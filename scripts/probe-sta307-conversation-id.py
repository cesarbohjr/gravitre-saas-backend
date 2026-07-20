#!/usr/bin/env python3
"""STA-307 issue #2 — conversation-id association check (prod).

Does NOT chase the hang. Only answers: did orchestration/plan state land under
the conversation_id we sent, or under a different conversation (cross-id)?

Steps:
1. Search recent prod rows for the high-intent HubSpot/Slack prompt (original
   repro hunt).
2. Controlled dual-conversation probe:
   - Create/use cid_target with distinctive title
   - Create cid_decoy with different title
   - POST chat to cid_target only
   - Compare messages / task_state / audit metadata conversation_id
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))
from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
    assert_conversation_create_allowed,
    mark_smoke_run,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

OUT = ROOT / "docs" / "delivery" / "sta307-conversation-id-check.json"
ORG = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
BASE = "https://gravitre-saas-backend-production.up.railway.app"
PROMPT = (
    "Search HubSpot for high-intent leads and draft a follow-up in Slack "
    "[STA-307-id-check {nonce}]"
)
CHAT_TIMEOUT = 180.0


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
                    "messageId": d.get("messageId"),
                    "dialogueMode": d.get("dialogueMode"),
                    "expl": (d.get("answerExplanation") or "")[:200],
                    "pending": d.get("pendingTask") or d.get("pending_task"),
                    "executionResult": d.get("executionResult") or d.get("execution_result"),
                    "taskStateKeys": list((d.get("taskState") or {}).keys())
                    if isinstance(d.get("taskState"), dict)
                    else None,
                }
            )
    return {"text": "".join(texts), "intel": intel}


def hunt_original(client, *, since_hours: int = 72) -> dict[str, Any]:
    since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
    # conversation_messages has no org_id — scope via org conversations first.
    org_conv_ids = [
        str(r["id"])
        for r in (
            client.table("conversations")
            .select("id")
            .eq("org_id", ORG)
            .gte("updated_at", since)
            .order("updated_at", desc=True)
            .limit(200)
            .execute()
            .data
            or []
        )
        if r.get("id")
    ]
    msg_rows: list[dict[str, Any]] = []
    # Chunk .in_ queries; filter high-intent in Python for reliability.
    for i in range(0, len(org_conv_ids), 50):
        chunk = org_conv_ids[i : i + 50]
        if not chunk:
            break
        rows = (
            client.table("conversation_messages")
            .select("id,conversation_id,role,content,created_at")
            .in_("conversation_id", chunk)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(100)
            .execute()
            .data
            or []
        )
        for m in rows:
            c = (m.get("content") or "").lower()
            if "high-intent" in c and "slack" in c:
                msg_rows.append(m)
    msg_rows = sorted(msg_rows, key=lambda m: str(m.get("created_at") or ""), reverse=True)[:30]
    # Broader title hunt
    conv_rows = (
        client.table("conversations")
        .select("id,title,preview,updated_at,task_state")
        .eq("org_id", ORG)
        .gte("updated_at", since)
        .or_("title.ilike.%high-intent%,title.ilike.%HubSpot%,preview.ilike.%high-intent%")
        .order("updated_at", desc=True)
        .limit(40)
        .execute()
        .data
        or []
    )
    orch_audits = (
        client.table("audit_events")
        .select("id,action,resource_type,resource_id,metadata,created_at")
        .eq("org_id", ORG)
        .gte("created_at", since)
        .or_(
            "action.ilike.%orchestr%,action.eq.tool.invoke.requested,"
            "action.eq.tool.invoke.completed,action.eq.tool.invoke.failed"
        )
        .order("created_at", desc=True)
        .limit(80)
        .execute()
        .data
        or []
    )
    # Filter audits that mention hubspot+slack or orchestration in metadata
    orch_hits = []
    for row in orch_audits:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        blob = json.dumps(meta, default=str).lower()
        if "orchestr" in blob or ("hubspot" in blob and "slack" in blob) or "connector_orchestration" in blob:
            orch_hits.append(
                {
                    "id": row.get("id"),
                    "action": row.get("action"),
                    "resource_id": row.get("resource_id"),
                    "created_at": row.get("created_at"),
                    "conversation_id": meta.get("conversation_id"),
                    "metadata_keys": sorted(meta.keys())[:24],
                }
            )

    # For each matching message, load owning conversation title
    message_hits = []
    for m in msg_rows[:15]:
        cid = m.get("conversation_id")
        conv = None
        if cid:
            rows = (
                client.table("conversations")
                .select("id,title,preview,updated_at")
                .eq("id", cid)
                .limit(1)
                .execute()
                .data
                or []
            )
            conv = rows[0] if rows else None
        message_hits.append(
            {
                "message_id": m.get("id"),
                "conversation_id": cid,
                "created_at": m.get("created_at"),
                "role": m.get("role"),
                "content_head": (m.get("content") or "")[:180],
                "conversation_title": (conv or {}).get("title"),
                "title_matches_prompt": bool(
                    conv
                    and "high-intent" in str(conv.get("title") or "").lower()
                ),
                "same_id_title_mismatch": bool(
                    conv
                    and cid
                    and "high-intent" in (m.get("content") or "").lower()
                    and "high-intent" not in str(conv.get("title") or "").lower()
                ),
            }
        )

    return {
        "since": since,
        "message_hits": message_hits,
        "conversation_title_hits": [
            {
                "id": c.get("id"),
                "title": c.get("title"),
                "preview": (c.get("preview") or "")[:120],
                "updated_at": c.get("updated_at"),
                "pending_type": ((c.get("task_state") or {}).get("pending_task") or {}).get("type")
                if isinstance(c.get("task_state"), dict)
                else None,
            }
            for c in conv_rows[:20]
        ],
        "orchestration_audit_hits": orch_hits[:30],
    }


async def controlled_probe(ac: AsyncClient, hdr: dict, client, actor: str) -> dict[str, Any]:
    nonce = uuid.uuid4().hex[:8]
    prompt = PROMPT.format(nonce=nonce)
    decoy_title = f"STA-307-DECOY {nonce} — unrelated Apollo list"
    target_title = f"STA-307-TARGET {nonce} — {prompt}"[:80]

    # Pre-create two conversations via direct insert (service role) so titles are known.
    assert_conversation_create_allowed(ORG)
    cid_target = str(uuid.uuid4())
    cid_decoy = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    for cid, title in ((cid_target, target_title), (cid_decoy, decoy_title)):
        client.table("conversations").insert(
            {
                "id": cid,
                "org_id": ORG,
                "user_id": actor,
                "title": title,
                "preview": title[:200],
                "message_count": 0,
                "task_state": {},
                "created_at": now,
                "updated_at": now,
            }
        ).execute()

    t0 = time.monotonic()
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": prompt}]}],
        "org_id": ORG,
        "tools": ["knowledge_base", "connector_status", "hubspot_search_contacts", "slack_post_message"],
        "mode": "standard",
        "conversation_id": cid_target,
    }
    try:
        r = await ac.post("/api/assistant/chat", json=body, headers=hdr, timeout=CHAT_TIMEOUT)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        parsed = parse_sse(r.text)
        http = r.status_code
        err = None
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        parsed = {"text": "", "intel": []}
        http = None
        err = f"{type(exc).__name__}: {exc}"

    # Reload both conversations + messages
    def load_conv(cid: str) -> dict[str, Any]:
        rows = (
            client.table("conversations")
            .select("id,title,preview,updated_at,task_state,message_count")
            .eq("id", cid)
            .limit(1)
            .execute()
            .data
            or []
        )
        msgs = (
            client.table("conversation_messages")
            .select("id,role,content,created_at")
            .eq("conversation_id", cid)
            .order("created_at", desc=False)
            .limit(20)
            .execute()
            .data
            or []
        )
        row = rows[0] if rows else {}
        ts = row.get("task_state") if isinstance(row.get("task_state"), dict) else {}
        pending = ts.get("pending_task") if isinstance(ts.get("pending_task"), dict) else None
        return {
            "id": cid,
            "title": row.get("title"),
            "message_count": row.get("message_count"),
            "updated_at": row.get("updated_at"),
            "pending_type": (pending or {}).get("type"),
            "pending_status": (pending or {}).get("status"),
            "step_labels": [
                s.get("label")
                for s in ((pending or {}).get("params") or {}).get("steps") or []
                if isinstance(s, dict)
            ][:8],
            "messages": [
                {
                    "id": m.get("id"),
                    "role": m.get("role"),
                    "content_head": (m.get("content") or "")[:160],
                    "created_at": m.get("created_at"),
                }
                for m in msgs
            ],
            "has_nonce_in_messages": any(nonce in (m.get("content") or "") for m in msgs),
            "has_prompt_in_messages": any("high-intent" in (m.get("content") or "").lower() for m in msgs),
        }

    target = load_conv(cid_target)
    decoy = load_conv(cid_decoy)

    # Audits since probe start mentioning either conversation id
    audits = (
        client.table("audit_events")
        .select("id,action,resource_id,metadata,created_at")
        .eq("org_id", ORG)
        .gte("created_at", now)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    audit_on_target = []
    audit_on_decoy = []
    audit_other = []
    for row in audits:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        meta_cid = str(meta.get("conversation_id") or "")
        blob = json.dumps({"a": row.get("action"), "m": meta, "r": row.get("resource_id")}, default=str)
        if cid_target not in blob and cid_decoy not in blob and nonce not in blob:
            continue
        slim = {
            "id": row.get("id"),
            "action": row.get("action"),
            "resource_id": row.get("resource_id"),
            "created_at": row.get("created_at"),
            "metadata_conversation_id": meta_cid or None,
        }
        if meta_cid == cid_target or cid_target in blob:
            audit_on_target.append(slim)
        elif meta_cid == cid_decoy or cid_decoy in blob:
            audit_on_decoy.append(slim)
        else:
            audit_other.append(slim)

    # Verdict rules for controlled probe
    leaked_to_decoy = bool(
        decoy["has_nonce_in_messages"]
        or decoy["has_prompt_in_messages"]
        or decoy["pending_type"]
        or audit_on_decoy
    )
    landed_on_target = bool(
        target["has_nonce_in_messages"]
        or target["has_prompt_in_messages"]
        or target["pending_type"]
        or audit_on_target
        or parsed["intel"]
    )
    if leaked_to_decoy:
        issue2 = "CONFIRMED_CROSS_CONVERSATION"
        severity = "P0_integrity"
    elif landed_on_target:
        issue2 = "REFUTED_for_controlled_probe"
        severity = "not_cross_id_in_this_probe"
    else:
        issue2 = "INCONCLUSIVE_no_durable_writes"
        severity = "need_ui_path_or_longer_repro"

    return {
        "nonce": nonce,
        "prompt": prompt,
        "cid_target": cid_target,
        "cid_decoy": cid_decoy,
        "target_title": target_title,
        "decoy_title": decoy_title,
        "http": http,
        "elapsed_ms": elapsed_ms,
        "error": err,
        "text_head": (parsed.get("text") or "")[:300],
        "intel_count": len(parsed.get("intel") or []),
        "last_intel": (parsed.get("intel") or [None])[-1],
        "target_after": target,
        "decoy_after": decoy,
        "audits_on_target": audit_on_target[:30],
        "audits_on_decoy": audit_on_decoy[:30],
        "audits_other_matching_nonce": audit_other[:20],
        "issue2_verdict": issue2,
        "severity_note": severity,
        "ui_title_hypothesis": (
            "Frontend ensureConversation only sets title on CREATE; submitting a new "
            "prompt into an existing thread keeps the old title with the SAME conversation_id "
            "(cosmetic mismatch). Controlled probe isolates whether durable writes jump ids."
        ),
    }


async def main() -> int:
    load_env()
    mark_smoke_run()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    env = {k: v for k, v in os.environ.items() if v}
    org_id, actor, email = resolve_isolated_conversation_actor(env, client)
    global ORG
    ORG = org_id
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
        **smoke_http_headers(),
    }

    report: dict[str, Any] = {
        "probe": "sta307_issue2_conversation_id",
        "ticket": "STA-307",
        "started_at": utcnow(),
        "org_id": ORG,
        "actor_id": actor,
        "base_url": BASE,
        "scope": "issue_2_only_no_hang_investigation",
    }

    async with AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT, verify=False) as ac:
        health = (await ac.get("/health")).json()
        report["prod_health"] = {"git_sha": health.get("git_sha"), "status": health.get("status")}
        report["original_repro_hunt"] = hunt_original(client, since_hours=96)
        report["controlled_probe"] = await controlled_probe(ac, hdr, client, actor)

    # Overall issue #2 answer
    hunt = report["original_repro_hunt"]
    ctrl = report["controlled_probe"]
    same_id_title_mismatches = [
        h for h in hunt.get("message_hits") or [] if h.get("same_id_title_mismatch")
    ]
    report["issue2_summary"] = {
        "original_session_ids_retrievable": bool(hunt.get("message_hits")),
        "same_id_title_mismatch_candidates": len(same_id_title_mismatches),
        "same_id_title_mismatch_samples": same_id_title_mismatches[:5],
        "controlled_probe_verdict": ctrl.get("issue2_verdict"),
        "definitive_for_this_report": ctrl.get("issue2_verdict"),
        "interpretation": None,
    }
    v = ctrl.get("issue2_verdict")
    if v == "CONFIRMED_CROSS_CONVERSATION":
        report["issue2_summary"]["interpretation"] = (
            "Durable writes or audits for the probe landed on the decoy conversation_id. "
            "This is a real cross-conversation attribution bug (P0). Escalate STA-307; "
            "review prior audit evidence that used conversation_id as the sole join key."
        )
    elif v == "REFUTED_for_controlled_probe":
        report["issue2_summary"]["interpretation"] = (
            "Controlled dual-conversation probe: all durable writes/audits stayed on the "
            "target conversation_id; decoy stayed clean. Cross-conversation attribution NOT "
            "reproduced. Title/label mismatch is consistent with cosmetic UI title not updating "
            "on existing threads (same id). Hang/label remain open under STA-307 but do not "
            "by themselves invalidate the audit chain's conversation_id joins."
        )
    else:
        report["issue2_summary"]["interpretation"] = (
            "Controlled probe did not leave durable target writes (clarification/early exit or "
            "timeout). Issue #2 not confirmed. Need UI-path repro or original session ids."
        )

    report["finished_at"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report["issue2_summary"], indent=2, default=str))
    print("CONTROLLED", ctrl.get("issue2_verdict"), "elapsed_ms", ctrl.get("elapsed_ms"))
    print("WROTE", OUT)
    return 0 if v != "CONFIRMED_CROSS_CONVERSATION" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
