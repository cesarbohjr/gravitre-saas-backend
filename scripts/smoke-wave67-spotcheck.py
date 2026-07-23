#!/usr/bin/env python3
"""Wave 6–7 live spot-check: capture SSE timestamps for the four UI claims.

Default: local ASGI (dev). Part C: pass --base-url to hit production API.

Usage:
  python scripts/smoke-wave67-spotcheck.py
  python scripts/smoke-wave67-spotcheck.py --base-url https://gravitre-saas-backend-production.up.railway.app
  python scripts/smoke-wave67-spotcheck.py --skip-write
"""
from __future__ import annotations

import argparse
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
from httpx import ASGITransport, AsyncClient

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

from isolated_conversation_org import (  # noqa: E402
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    mark_smoke_run,
    smoke_http_headers,
)

ORG_DEFAULT = DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
PROD_DEFAULT = "https://gravitre-saas-backend-production.up.railway.app"


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


def _summarize_stream(events: list[dict[str, Any]], wall_start: str) -> dict[str, Any]:
    timeline: list[dict[str, Any]] = []
    first_plan: dict[str, Any] | None = None
    first_tool_start: dict[str, Any] | None = None
    first_tool_complete: dict[str, Any] | None = None
    first_text: dict[str, Any] | None = None
    final_meta: dict[str, Any] | None = None
    tool_completes: list[dict[str, Any]] = []
    execution_results: list[dict[str, Any]] = []
    pending_tasks: list[dict[str, Any]] = []

    for idx, ev in enumerate(events):
        et = _event_type(ev)
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        entry = {"i": idx, "type": et}
        if et in {"data-intelligence", "intelligence-metadata", "data-assistant-metadata"}:
            expl = data.get("answerExplanation") or data.get("answer_explanation")
            task_state = data.get("taskState") or data.get("task_state")
            strategic = data.get("strategicPlan") or data.get("strategic_plan")
            exec_res = data.get("executionResult") or data.get("execution_result")
            pending = data.get("pendingTask") or data.get("pending_task")
            dialogue = data.get("dialogueMode") or data.get("dialogue_mode")
            entry.update(
                {
                    "answerExplanation": expl,
                    "dialogueMode": dialogue,
                    "has_current_plan": bool(
                        isinstance(task_state, dict) and task_state.get("current_plan")
                    )
                    or bool(strategic),
                    "has_execution_result": bool(exec_res),
                    "has_pending_task": bool(pending),
                }
            )
            if exec_res and isinstance(exec_res, dict):
                execution_results.append(
                    {
                        "i": idx,
                        "success": exec_res.get("success"),
                        "result_url": exec_res.get("result_url") or exec_res.get("resultUrl"),
                        "error_code": exec_res.get("error_code") or exec_res.get("errorCode"),
                        "assumption_notes": exec_res.get("assumption_notes")
                        or exec_res.get("assumptionNotes"),
                        "body": str(exec_res.get("body") or "")[:200],
                    }
                )
            if pending:
                pending_tasks.append({"i": idx, "pending": pending})
            if (expl and "Plan ready" in str(expl)) or entry["has_current_plan"]:
                if first_plan is None:
                    first_plan = {**entry, "wall_start": wall_start}
            if idx == len(events) - 1 or dialogue:
                final_meta = entry
        elif "tool-input" in et or et.endswith("tool-input-start") or "tool-call" in et:
            # Flat SSE: {type, toolCallId, toolName, input} — not nested under data.
            tool_name = data.get("toolName") or ev.get("toolName")
            if first_tool_start is None:
                first_tool_start = {"i": idx, "type": et, "toolName": tool_name}
            entry["toolName"] = tool_name
        elif "tool-output" in et or "tool-result" in et or et.endswith("tool-output-available"):
            # Flat SSE: {type, toolCallId, output:{errorCode,success,...}}
            output = data.get("output") if isinstance(data.get("output"), dict) else None
            if output is None and isinstance(ev.get("output"), dict):
                output = ev.get("output")
            if output is None and isinstance(data, dict) and (
                "errorCode" in data or "error_code" in data or "success" in data
            ):
                output = data
            shaped = {
                "i": idx,
                "type": et,
                "toolName": data.get("toolName") or ev.get("toolName"),
                "errorCode": (output or {}).get("errorCode") or (output or {}).get("error_code")
                if isinstance(output, dict)
                else None,
                "success": (output or {}).get("success") if isinstance(output, dict) else None,
                "error": str((output or {}).get("error") or "")[:180]
                if isinstance(output, dict)
                else None,
            }
            tool_completes.append(shaped)
            if first_tool_complete is None:
                first_tool_complete = shaped
            entry.update(shaped)
        elif et in {"text-start", "text-delta"}:
            if first_text is None:
                first_text = {"i": idx, "type": et}
        timeline.append(entry)

    return {
        "wall_start": wall_start,
        "event_count": len(events),
        "first_plan_sse": first_plan,
        "first_tool_start_sse": first_tool_start,
        "first_tool_complete_sse": first_tool_complete,
        "first_text_sse": first_text,
        "final_meta_sse": final_meta,
        "tool_completes": tool_completes,
        "execution_results": execution_results,
        "pending_tasks": pending_tasks,
        "plan_before_tools": bool(
            first_plan
            and first_tool_start
            and int(first_plan.get("i", 10**9)) < int(first_tool_start.get("i", -1))
        ),
        "plan_only_in_final": bool(
            first_plan
            and first_tool_start
            and int(first_plan.get("i", -1)) > int(first_tool_start.get("i", 10**9))
        ),
        "timeline_abbrev": timeline[:80],
    }


async def _chat(
    ac: AsyncClient,
    *,
    org_id: str,
    token: str,
    text: str,
    conversation_id: str | None,
    tools: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]], str]:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": text}]}],
        "org_id": org_id,
        "tools": tools
        or [
            "knowledge_base",
            "agent_status",
            "connector_status",
            "apollo_lists_create",
            "apollo_lists_list",
            "slack_post_message",
        ],
        "mode": "reasoning",
    }
    if conversation_id:
        body["conversation_id"] = conversation_id
    wall = datetime.now(timezone.utc).isoformat()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        **smoke_http_headers(),
    }
    # Stream accumulate — prod sometimes closes chunked SSE early; keep partial body.
    chunks: list[bytes] = []
    status = "http_000"
    try:
        async with ac.stream(
            "POST",
            "/api/assistant/chat",
            json=body,
            headers=headers,
            timeout=180.0,
        ) as r:
            status = f"http_{r.status_code}"
            async for part in r.aiter_bytes():
                chunks.append(part)
    except Exception as exc:  # noqa: BLE001 — prefer partial SSE over hard fail
        if not chunks:
            raise
        print(f"WARN chat stream truncated ({exc}); using {sum(len(c) for c in chunks)} bytes")
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    events = _parse_sse(raw)
    return wall, events, status


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    mark_smoke_run()
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.workflows.repository import get_supabase_client
    from app.config import get_settings
    from smoke_auth import resolve_smoke_actor_and_email

    settings = get_settings()
    client = get_supabase_client(settings)
    org_id = (args.org_id or env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or ORG_DEFAULT).strip()
    env.setdefault(
        "ISOLATED_CONVERSATION_TEST_USER_ID",
        env.get("OAUTH_SMOKE_USER_ID") or "",
    )
    actor, email = resolve_smoke_actor_and_email(client, org_id=org_id, env=env)
    token = _mint_token(env, actor, email)
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    list_name = f"gravitre-wave67-spotcheck-{day}"
    conv = str(uuid.uuid4())
    base_url = (args.base_url or "").strip().rstrip("/")
    against_prod = bool(base_url)

    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "actor_id": actor,
        "conversation_id": conv,
        "list_name": list_name,
        "base_url": base_url or "local-asgi",
        "branch_note": (
            f"production API {base_url}"
            if against_prod
            else "local ASGI — not production API"
        ),
        "claims": {},
    }

    if against_prod:
        # Confirm deployed SHA when possible
        try:
            async with AsyncClient(base_url=base_url, timeout=30.0) as hc:
                hr = await hc.get("/health")
                report["prod_health"] = hr.json() if hr.status_code == 200 else {"http": hr.status_code}
        except Exception as exc:  # noqa: BLE001
            report["prod_health"] = {"error": str(exc)}

    if against_prod:
        client_cm = AsyncClient(base_url=base_url, timeout=180.0)
    else:
        from app.main import app

        client_cm = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=180.0,
        )

    async with client_cm as ac:
        # Claim 1 + success half of claim 2: plan + tool path (read first to avoid write)
        wall1, events1, status1 = await _chat(
            ac,
            org_id=org_id,
            token=token,
            conversation_id=conv,
            text=(
                f"Using Apollo, list my contact lists and summarize the first few names. "
                f"Then outline a short plan before calling tools. (wave67 plan/read {uuid.uuid4().hex[:8]})"
            ),
        )
        s1 = _summarize_stream(events1, wall1)
        report["turn_plan_read"] = {"http": status1, "summary": s1}
        print("TURN1 plan/read", status1, "events", s1["event_count"], "plan_before_tools", s1["plan_before_tools"])

        # Claim 2 failure: Slack expired
        wall2, events2, status2 = await _chat(
            ac,
            org_id=org_id,
            token=token,
            conversation_id=conv,
            text=(
                "Post a Slack message to the default channel saying "
                "'gravitre-wave67-spotcheck failure probe — ignore'. Use the Slack connector."
            ),
            tools=["slack_post_message", "connector_status", "knowledge_base"],
        )
        s2 = _summarize_stream(events2, wall2)
        report["turn_slack_fail"] = {"http": status2, "summary": s2}
        fail_codes = [
            t.get("errorCode") for t in s2.get("tool_completes") or [] if t.get("errorCode")
        ]
        print("TURN2 slack", status2, "errorCodes", fail_codes)

        if not args.skip_write:
            # Claim 3: write approval path (explicit name — not claim 4)
            wall3, events3, status3 = await _chat(
                ac,
                org_id=org_id,
                token=token,
                conversation_id=conv,
                text=(
                    f"Create an Apollo contact list named exactly '{list_name}'. "
                    "Do not invent a different name."
                ),
                tools=["apollo_lists_create", "apollo_lists_list", "connector_status", "knowledge_base"],
            )
            s3 = _summarize_stream(events3, wall3)
            report["turn_apollo_write_gate"] = {"http": status3, "summary": s3}
            print(
                "TURN3 apollo gate",
                status3,
                "pending",
                bool(s3.get("pending_tasks")),
                "exec",
                s3.get("execution_results"),
            )

            # Approve via chat "yes" when gated (works on prod API); fall back to local execute_plan only on ASGI.
            approve_conv = conv
            wall_yes, events_yes, status_yes = await _chat(
                ac,
                org_id=org_id,
                token=token,
                conversation_id=approve_conv,
                text="yes",
                tools=["apollo_lists_create", "apollo_lists_list", "connector_status", "knowledge_base"],
            )
            s_yes = _summarize_stream(events_yes, wall_yes)
            report["turn_apollo_approve"] = {"http": status_yes, "summary": s_yes}
            yes_exec = (s_yes.get("execution_results") or [None])[-1] if s_yes.get("execution_results") else None
            if yes_exec and yes_exec.get("success"):
                report["approved_execution"] = {
                    "user_approval_at": wall_yes,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "success": yes_exec.get("success"),
                    "error_code": yes_exec.get("error_code"),
                    "result_url": yes_exec.get("result_url"),
                    "assumption_notes": yes_exec.get("assumption_notes"),
                    "body": str(yes_exec.get("body") or "")[:300],
                    "via": "chat_yes",
                }
                print("APPROVED via chat yes", yes_exec.get("result_url"))
            elif not against_prod:
                # Local ASGI fallback: ReAct gate + execute_plan (same as prior probe)
                from app.operators.react_engine import ReActEngine, ReActResult, ReActStatus
                from app.services.chat_connector_execution_service import (
                    ChatConnectorExecutionService,
                    get_chat_connector_execution_service,
                )
                from app.services.conversation_state_service import get_conversation_state_service
                from app.services.react_write_gate import (
                    WRITE_APPROVAL_REQUIRED,
                    plan_from_react_write,
                    pending_write_from_react,
                )
                from app.services.tool_registry import get_tool_registry
                from app.services.tool_types import ToolContext

                reg = get_tool_registry()
                engine = ReActEngine(settings=settings, registry=reg)
                ctx = ToolContext(
                    settings=settings,
                    client=client,
                    org_id=org_id,
                    actor_id=actor,
                    agent_id="synthetic-default",
                    environment_name="production",
                )
                blocked = await engine._execute_tool_call(
                    ctx,
                    "apollo_lists_create",
                    {"name": list_name, "modality": "contacts"},
                    allowed_tool_names={"apollo_lists_create"},
                )
                gate_at = datetime.now(timezone.utc).isoformat()
                report["react_gate"] = {
                    "at": gate_at,
                    "error_code": blocked.get("error_code"),
                    "pending_approval": blocked.get("pending_approval"),
                }
                if blocked.get("error_code") == WRITE_APPROVAL_REQUIRED:
                    react_result = ReActResult(
                        status=ReActStatus.NEEDS_HUMAN_INPUT,
                        answer="Write requires approval",
                        tool_calls=[
                            {
                                "tool": "apollo_lists_create",
                                "args": {"name": list_name, "modality": "contacts"},
                                "result": blocked,
                            }
                        ],
                    )
                    pending = pending_write_from_react(react_result)
                    plan = plan_from_react_write(pending, reg)
                    state = get_conversation_state_service(settings)
                    await state.update_task_state(
                        conv,
                        org_id,
                        {
                            "pending_task": {
                                "type": "connector_action",
                                "status": "awaiting_confirm",
                                "params": {
                                    **ChatConnectorExecutionService.plan_to_dict(plan),
                                    "status": "awaiting_confirm",
                                    "source": "react_write_gate",
                                },
                            }
                        },
                        client=client,
                    )
                    approve_at = datetime.now(timezone.utc).isoformat()
                    svc = get_chat_connector_execution_service(settings)
                    result = await svc.execute_plan(
                        org_id=org_id,
                        user_id=actor,
                        conversation_id=conv,
                        plan=plan,
                        client=client,
                        classification={"intent": "connector_action", "requires_approval": True},
                        environment_name="production",
                    )
                    done_at = datetime.now(timezone.utc).isoformat()
                    report["approved_execution"] = {
                        "user_approval_at": approve_at,
                        "completed_at": done_at,
                        "success": result.success,
                        "error_code": result.error_code,
                        "result_url": result.result_url,
                        "entity_id": result.entity_id,
                        "assumption_notes": result.assumption_notes,
                        "body": (result.body or "")[:300],
                        "via": "local_execute_plan",
                    }
                    print(
                        "APPROVED",
                        result.success,
                        result.result_url,
                        "assumptions",
                        result.assumption_notes,
                    )

            # Claim 4 causal: omit-name create → inferred default → approve → assumption_notes
            conv4 = str(uuid.uuid4())
            wall4, events4, status4 = await _chat(
                ac,
                org_id=org_id,
                token=token,
                conversation_id=conv4,
                text="In Apollo, create a contact list.",
                tools=["apollo_lists_create", "apollo_lists_list", "connector_status", "knowledge_base"],
            )
            s4 = _summarize_stream(events4, wall4)
            report["turn_claim4_omit_name"] = {
                "http": status4,
                "summary": s4,
                "user_message": "In Apollo, create a contact list.",
            }
            print(
                "TURN4 omit-name",
                status4,
                "pending",
                bool(s4.get("pending_tasks")),
                "dialogue",
                (s4.get("final_meta_sse") or {}).get("dialogueMode"),
            )
            wall4b, events4b, status4b = await _chat(
                ac,
                org_id=org_id,
                token=token,
                conversation_id=conv4,
                text="yes",
                tools=["apollo_lists_create", "apollo_lists_list", "connector_status", "knowledge_base"],
            )
            s4b = _summarize_stream(events4b, wall4b)
            report["turn_claim4_approve"] = {"http": status4b, "summary": s4b}
            claim4_exec = None
            for er in s4b.get("execution_results") or []:
                claim4_exec = er
            report["claim4_execution"] = claim4_exec
            print(
                "TURN4 approve",
                status4b,
                "assumption_notes",
                (claim4_exec or {}).get("assumption_notes"),
                "url",
                (claim4_exec or {}).get("result_url"),
            )

    # Claim scoring from captured data
    t1 = report.get("turn_plan_read", {}).get("summary") or {}
    claim1 = {
        "status": "PASS"
        if t1.get("plan_before_tools")
        else ("PARTIAL" if t1.get("first_plan_sse") else "FAIL"),
        "evidence": {
            "first_plan_sse": t1.get("first_plan_sse"),
            "first_tool_start_sse": t1.get("first_tool_start_sse"),
            "plan_before_tools": t1.get("plan_before_tools"),
            "plan_only_in_final": t1.get("plan_only_in_final"),
            "wall_start": t1.get("wall_start"),
        },
    }
    if t1.get("first_plan_sse") and not t1.get("first_tool_start_sse"):
        claim1["status"] = "PARTIAL"
        claim1["note"] = "Plan SSE seen but no tool-start in this turn (tools may have been skipped)"

    t2 = report.get("turn_slack_fail", {}).get("summary") or {}
    fail_chip = next(
        (t for t in (t2.get("tool_completes") or []) if t.get("errorCode") or t.get("success") is False),
        None,
    )
    success_chip = next(
        (t for t in (t1.get("tool_completes") or []) if t.get("success") is True),
        None,
    )
    claim2 = {
        "status": "PASS"
        if success_chip and fail_chip and fail_chip.get("errorCode")
        else ("PARTIAL" if fail_chip or success_chip else "FAIL"),
        "evidence": {
            "success_chip": success_chip,
            "failure_chip": fail_chip,
            "success_before_text": bool(
                success_chip
                and t1.get("first_text_sse")
                and int(success_chip.get("i", 10**9)) < int((t1.get("first_text_sse") or {}).get("i", -1))
            ),
            "slack_wall_start": t2.get("wall_start"),
        },
    }

    approved = report.get("approved_execution") or {}
    url = str(approved.get("result_url") or "")
    url_ok = bool(url) and "/connectors/" not in url and url.startswith("http")
    claim3 = {
        "status": "PASS"
        if approved.get("success") and url_ok
        else ("PARTIAL" if approved else "NOT_RUN" if args.skip_write else "FAIL"),
        "evidence": {
            "react_gate": report.get("react_gate"),
            "approved_execution": approved,
            "result_url_is_deep_link": url_ok,
            "not_connector_conflation": "/connectors/" not in url,
        },
    }

    claim4_exec = report.get("claim4_execution") or {}
    notes = claim4_exec.get("assumption_notes") or approved.get("assumption_notes")
    # Also scan SSE execution_results
    sse_notes = []
    for turn_key in (
        "turn_plan_read",
        "turn_slack_fail",
        "turn_apollo_write_gate",
        "turn_apollo_approve",
        "turn_claim4_omit_name",
        "turn_claim4_approve",
    ):
        for er in ((report.get(turn_key) or {}).get("summary") or {}).get("execution_results") or []:
            if er.get("assumption_notes"):
                sse_notes.append(er)
    omit_pending = bool(((report.get("turn_claim4_omit_name") or {}).get("summary") or {}).get("pending_tasks"))
    causal_notes = bool(notes) and any("MSP Prospects" in str(n) or "Assumed" in str(n) for n in (notes if isinstance(notes, list) else [notes]))
    claim4 = {
        "status": "PASS"
        if (causal_notes or sse_notes) and (omit_pending or claim4_exec.get("success"))
        else ("PARTIAL" if notes or sse_notes or omit_pending else "FAIL"),
        "evidence": {
            "omit_name_pending": omit_pending,
            "claim4_execution": claim4_exec,
            "execution_result_assumption_notes": notes,
            "sse_execution_results_with_notes": sse_notes,
            "note": (
                "PASS requires omit-name turn → inferred plan and/or assumption_notes on prod SSE. "
                "PARTIAL if only non-causal notes or gate without notes."
            ),
        },
    }

    report["claims"] = {
        "1_plan_before_tools": claim1,
        "2_tool_chips_error_code": claim2,
        "3_approval_panel_result_url": claim3,
        "4_assumption_notes_ui": claim4,
    }
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--skip-write", action="store_true")
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"Hit remote API instead of local ASGI (e.g. {PROD_DEFAULT})",
    )
    parser.add_argument(
        "--json",
        default=str(REPO / "docs" / "delivery" / "wave67-spotcheck-latest.json"),
    )
    args = parser.parse_args()
    report = asyncio.run(main_async(args))
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("WROTE", out)
    print("CLAIMS", json.dumps(report["claims"], indent=2, default=str))
    statuses = [c.get("status") for c in report["claims"].values()]
    if "FAIL" in statuses:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
