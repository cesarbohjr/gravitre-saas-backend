#!/usr/bin/env python3
"""Part 1 — Live audit of post-action UX (write/read/swarm/fail/recs).

Isolated org only. Writes docs/delivery/post-action-experience-audit-live.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from gravitree_test_client import (  # noqa: E402
    get_service_client,
    load_env,
    require_isolated_org,
    resolve_test_actor,
    smoke_http_headers,
)

BASE = os.environ.get("POST_ACTION_BASE", "https://api.gravitre.app").rstrip("/")
ENV = "production"
OUT = REPO / "docs" / "delivery" / "post-action-experience-audit-live.json"
SWARM_ID = "c54ddbe8-ec0b-4f0f-bebc-d6d4389c4c65"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def mint(env, user_id, email):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 7200,
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def health():
    with urllib.request.urlopen(urllib.request.Request(f"{BASE}/health"), timeout=30) as resp:
        return json.loads(resp.read().decode())


def req(method, path, token, org_id, body=None, timeout=180):
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    r.add_header("Authorization", f"Bearer {token}")
    r.add_header("X-Org-Id", org_id)
    r.add_header("X-Environment", ENV)
    for k, v in smoke_http_headers().items():
        r.add_header(k, v)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    intel: list[dict] = []
    suggestions: list[str] = []
    for line in (raw or "").splitlines():
        if not line.startswith("data:"):
            continue
        p = line[5:].strip()
        if not p or p == "[DONE]":
            continue
        try:
            o = json.loads(p)
        except json.JSONDecodeError:
            continue
        typ = str(o.get("type") or "")
        data = o.get("data") if isinstance(o.get("data"), dict) else {}
        if typ == "text-delta":
            texts.append(o.get("delta") or data.get("delta") or "")
        elif typ == "data-intelligence":
            intel.append(data)
        elif typ == "data-suggestions":
            for s in data.get("suggestions") or o.get("suggestions") or []:
                if isinstance(s, str):
                    suggestions.append(s)
                elif isinstance(s, dict) and s.get("text"):
                    suggestions.append(str(s["text"]))
    exec_result = None
    pending = None
    for row in reversed(intel):
        if row.get("executionResult") and exec_result is None:
            exec_result = row.get("executionResult")
        if row.get("pendingTask") and pending is None:
            pending = row.get("pendingTask")
        ts = row.get("taskState") if isinstance(row.get("taskState"), dict) else {}
        if not pending and isinstance(ts.get("pending_task"), dict):
            pending = ts.get("pending_task")
    return {
        "text": "".join(texts),
        "intel": intel,
        "execution_result": exec_result,
        "pending_task": pending,
        "suggestions": suggestions,
    }


def chat(token, org_id, messages, conversation_id):
    body = {
        "messages": messages,
        "org_id": org_id,
        "mode": "agent",
        "conversation_id": conversation_id,
        "tools": ["connector_status", "web_search", "create_workflow", "execute_workflow"],
    }
    st, raw = req("POST", "/api/assistant/chat", token, org_id, body, timeout=180)
    parsed = parse_sse(raw if st == 200 else "")
    return {"http": st, "raw_len": len(raw or ""), **parsed}


def new_conv(token, org_id, title):
    st, raw = req(
        "POST",
        "/api/conversations",
        token,
        org_id,
        {"org_id": org_id, "title": title[:80]},
        timeout=60,
    )
    data = json.loads(raw) if raw.startswith("{") else {}
    if st >= 400:
        raise RuntimeError(f"create conv {st}: {raw[:300]}")
    return str(data.get("id") or "")


def has_http_url(text: str) -> bool:
    return bool(re.search(r"https?://\S+", text or ""))


def score_write(case: dict) -> str:
    text = case.get("assistant_text") or ""
    er = case.get("execution_result") if isinstance(case.get("execution_result"), dict) else {}
    ext = (
        er.get("external_url")
        or er.get("externalUrl")
        or (er.get("structured") or {}).get("external_url")
        or (er.get("structured") or {}).get("externalUrl")
    )
    result_url = er.get("result_url") or er.get("resultUrl")
    vendor_link = bool(ext) or bool(re.search(r"apollo\.io|hubspot\.com|slack\.com", text, re.I))
    preview_ok = case.get("preview_has_live_fields") is True
    audit_in_chat = bool(result_url) or "audit" in text.lower() or "/runs/" in text
    if vendor_link and (er.get("success") is True or "created" in text.lower()):
        if preview_ok and audit_in_chat:
            return "PASS"
        return "PARTIAL"
    if er.get("success") is False and case.get("gated"):
        return "PARTIAL"  # approval gate, not completion
    return "FAIL"


def main() -> int:
    env = load_env()
    org_id, user_id, email = resolve_test_actor(env)
    org_id = require_isolated_org(org_id)
    client = get_service_client(env)
    token = mint(env, user_id, email)
    tip = health()
    sha = str(tip.get("git_sha") or "")[:12]
    findings: dict[str, Any] = {
        "probe": "post_action_experience_audit",
        "verified_at": utcnow(),
        "git_sha": sha,
        "base": BASE,
        "org_id": org_id,
        "user_id": user_id,
        "cases": {},
    }

    # ── 1 WRITE: Apollo list create ──────────────────────────────────
    list_name = f"PostAction-Audit-{uuid.uuid4().hex[:8]}"
    cid_w = new_conv(token, org_id, f"post-action write {list_name}")
    msgs = [
        {
            "role": "user",
            "parts": [
                {
                    "type": "text",
                    "text": (
                        f"Create a new Apollo contact list named '{list_name}'. "
                        "Do not add contacts."
                    ),
                }
            ],
        }
    ]
    plan = chat(token, org_id, msgs, cid_w)
    msgs.append({"role": "assistant", "parts": [{"type": "text", "text": plan["text"] or ""}]})
    # Confirm if pending
    pending = plan.get("pending_task") or {}
    if pending or "yes" in (plan["text"] or "").lower() or "approve" in (plan["text"] or "").lower():
        msgs.append({"role": "user", "parts": [{"type": "text", "text": "approve"}]})
        done = chat(token, org_id, msgs, cid_w)
    else:
        done = plan
    er = done.get("execution_result") if isinstance(done.get("execution_result"), dict) else {}
    msgs.append({"role": "assistant", "parts": [{"type": "text", "text": done["text"] or ""}]})
    msgs.append(
        {
            "role": "user",
            "parts": [
                {
                    "type": "text",
                    "text": "Show me what that looks like — pull the live list details from Apollo.",
                }
            ],
        }
    )
    preview = chat(token, org_id, msgs, cid_w)
    preview_text = preview["text"] or ""
    preview_live = bool(
        re.search(r"\b(list|id|name|contacts?|members?)\b", preview_text, re.I)
        and (
            list_name.lower() in preview_text.lower()
            or re.search(r"\b[a-f0-9]{20,}\b", preview_text)
            or "apollo" in preview_text.lower()
        )
        and "don't have enough" not in preview_text.lower()
    )
    write_case = {
        "conversation_id": cid_w,
        "list_name": list_name,
        "plan_excerpt": (plan["text"] or "")[:500],
        "assistant_text": (done["text"] or "")[:800],
        "execution_result": {
            "success": er.get("success"),
            "title": er.get("title") or er.get("task_label"),
            "body": (er.get("body") or "")[:400],
            "result_url": er.get("result_url") or er.get("resultUrl"),
            "external_url": er.get("external_url")
            or er.get("externalUrl")
            or (er.get("structured") or {}).get("external_url"),
            "error_code": er.get("error_code") or er.get("errorCode"),
        },
        "suggestions_after_write": done.get("suggestions") or [],
        "preview_request": "Show me what that looks like — pull the live list details from Apollo.",
        "preview_excerpt": preview_text[:800],
        "preview_has_live_fields": preview_live,
        "has_vendor_http_link_in_text": has_http_url(done["text"] or ""),
        "gated": bool(pending) and er.get("success") is not True,
    }
    write_case["verdict"] = score_write(write_case)
    findings["cases"]["write_apollo_list"] = write_case

    # ── 2 READ: connector status ─────────────────────────────────────
    cid_r = new_conv(token, org_id, "post-action read status")
    read = chat(
        token,
        org_id,
        [
            {
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": "What connectors are Connected right now? List them with health.",
                    }
                ],
            }
        ],
        cid_r,
    )
    read_text = read["text"] or ""
    actionable = bool(
        re.search(r"\b(apollo|connected|healthy)\b", read_text, re.I)
        and (
            re.search(r"\b(next|create|list|search|connect)\b", read_text, re.I)
            or (read.get("suggestions") or [])
        )
    )
    findings["cases"]["read_connector_status"] = {
        "conversation_id": cid_r,
        "assistant_text": read_text[:800],
        "suggestions": read.get("suggestions") or [],
        "structured_enough_to_act": actionable,
        "verdict": "PASS" if actionable else ("PARTIAL" if "apollo" in read_text.lower() else "FAIL"),
    }

    # ── 3 SWARM: fetch existing lifecycle run ────────────────────────
    st, raw = req("GET", f"/api/agents/swarm/{SWARM_ID}", token, org_id, timeout=60)
    swarm = json.loads(raw) if raw.startswith("{") else {"_raw": raw[:500]}
    subtasks = swarm.get("subtasks") or swarm.get("tasks") or []
    if not subtasks and isinstance(swarm.get("data"), dict):
        subtasks = swarm["data"].get("subtasks") or []
    final_rec = (
        swarm.get("finalRecommendation")
        or swarm.get("final_recommendation")
        or (swarm.get("aggregateResult") or {}).get("finalRecommendation")
        or ""
    )
    # Chat surface: ask about that swarm in a new conversation
    cid_s = new_conv(token, org_id, "post-action swarm visibility")
    swarm_chat = chat(
        token,
        org_id,
        [
            {
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": (
                            f"Summarize swarm run {SWARM_ID}: what did Sales find vs Marketing, "
                            "with evidence for each agent — not just the final recommendation."
                        ),
                    }
                ],
            }
        ],
        cid_s,
    )
    stext = swarm_chat["text"] or ""
    has_sales = bool(re.search(r"\bsales\b", stext, re.I))
    has_mkt = bool(re.search(r"\bmarketing\b", stext, re.I))
    has_both_evidence = has_sales and has_mkt and (
        "crm" in stext.lower() or "apollo" in stext.lower() or "blocker" in stext.lower()
        or "framing" in stext.lower()
    )
    findings["cases"]["swarm_step_transparency"] = {
        "swarm_id": SWARM_ID,
        "api_http": st,
        "api_subtask_count": len(subtasks) if isinstance(subtasks, list) else 0,
        "api_final_recommendation_excerpt": str(final_rec)[:400],
        "api_has_per_subtask_bodies": bool(
            isinstance(subtasks, list)
            and len(subtasks) >= 2
            and any((t.get("result") or t.get("summary") or t.get("finding")) for t in subtasks if isinstance(t, dict))
        ),
        "chat_conversation_id": cid_s,
        "chat_excerpt": stext[:900],
        "chat_shows_sales_and_marketing": has_both_evidence,
        "verdict": "PASS"
        if has_both_evidence
        else ("PARTIAL" if has_sales or has_mkt else "FAIL"),
    }

    # ── 4 FAILURE: cold connector ────────────────────────────────────
    cid_f = new_conv(token, org_id, "post-action fail zendesk")
    fail = chat(
        token,
        org_id,
        [
            {
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": "Create a Zendesk ticket titled 'Post-action audit failure probe'.",
                    }
                ],
            }
        ],
        cid_f,
    )
    ftext = fail["text"] or ""
    fer = fail.get("execution_result") if isinstance(fail.get("execution_result"), dict) else {}
    specific_why = bool(
        re.search(r"zendesk|connect|/connectors|not connected|unavailable", ftext, re.I)
        or fer.get("error_code")
        or fer.get("connector_management_url")
        or fer.get("connectorManagementUrl")
    )
    one_next = bool(
        re.search(r"connect|reconnect|/connectors|would you like", ftext, re.I)
        or fer.get("connector_management_url")
        or fer.get("connectorManagementUrl")
    )
    findings["cases"]["failure_zendesk"] = {
        "conversation_id": cid_f,
        "assistant_text": ftext[:800],
        "execution_result": {
            "success": fer.get("success"),
            "error_code": fer.get("error_code") or fer.get("errorCode"),
            "body": (fer.get("body") or "")[:400],
            "connector_management_url": fer.get("connector_management_url")
            or fer.get("connectorManagementUrl"),
        },
        "specific_actionable_why": specific_why,
        "single_next_action_offered": one_next,
        "verdict": "PASS" if specific_why and one_next else ("PARTIAL" if specific_why else "FAIL"),
    }

    # ── 5 RECOMMENDATIONS after write ────────────────────────────────
    # Check intelligence heuristics endpoint + whether write SSE included recs
    st_h, raw_h = req("GET", "/api/intelligence/recommendations/heuristics", token, org_id, timeout=60)
    heur = json.loads(raw_h) if raw_h.startswith("{") else {}
    cards = heur.get("cards") or heur.get("recommendations") or []
    write_suggestions = write_case.get("suggestions_after_write") or []
    findings["cases"]["recommendations_on_completion"] = {
        "heuristics_http": st_h,
        "heuristics_card_count": len(cards) if isinstance(cards, list) else 0,
        "heuristics_sample": (cards[0] if isinstance(cards, list) and cards else None),
        "chat_suggestions_after_write": write_suggestions,
        "wired_into_write_completion_sse": bool(write_suggestions),
        "verdict": "PASS"
        if write_suggestions
        else ("PARTIAL" if isinstance(cards, list) and cards else "FAIL"),
    }

    # Optional: notification fanout check for write
    try:
        notes = (
            client.table("notifications")
            .select("id,title,body,created_at,link")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        findings["recent_notifications"] = notes.data or []
    except Exception as exc:  # noqa: BLE001
        findings["recent_notifications_error"] = str(exc)[:200]

    verdicts = {k: v.get("verdict") for k, v in findings["cases"].items()}
    if all(v == "PASS" for v in verdicts.values()):
        findings["overall"] = "PASS"
    elif any(v == "FAIL" for v in verdicts.values()):
        findings["overall"] = "FAIL"
    else:
        findings["overall"] = "PARTIAL"
    findings["verdicts"] = verdicts
    OUT.write_text(json.dumps(findings, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"overall": findings["overall"], "verdicts": verdicts, "git_sha": sha, "artifact": str(OUT)}, indent=2))
    return 0 if findings["overall"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
