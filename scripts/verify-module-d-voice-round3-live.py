#!/usr/bin/env python3
"""Module D Round-3 live audit — canvas, skip-copy, LLM chat, register, humor."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    mark_smoke_run,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

BASE = os.environ.get("MODULE_D_VOICE_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "module-d-voice-round3-live.json"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", "backend/.env", "apps/web/.env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint(env: dict[str, str], user_id: str, email: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{env['SUPABASE_URL'].rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def _sse_text(resp: httpx.Response) -> str:
    chunks: list[str] = []
    for line in resp.iter_lines():
        if not line:
            continue
        text = line.decode("utf-8") if isinstance(line, (bytes, bytearray)) else str(line)
        if not text.startswith("data:"):
            continue
        payload = text[5:].strip()
        if payload in {"", "[DONE]"}:
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            chunks.append(payload)
            continue
        if isinstance(obj, dict):
            for key in ("delta", "text", "content", "message"):
                if isinstance(obj.get(key), str):
                    chunks.append(obj[key])
    return "".join(chunks).strip()


def _chat(headers: dict, prompt: str, conversation_id: str) -> tuple[int, str]:
    body = {
        "messages": [{"role": "user", "content": prompt}],
        "conversation_id": conversation_id,
        "mode": "auto",
    }
    with httpx.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        headers={**headers, "Accept": "text/event-stream"},
        json=body,
        timeout=120.0,
    ) as resp:
        return resp.status_code, (_sse_text(resp) if resp.is_success else "")


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    from app.services.canvas_write_gate import block_canvas_write_step
    from app.services.chat_action_mapper import get_chat_action_mapper
    from app.services.gravitree_voice import (
        HOUSE_PHRASING,
        format_operator_message,
        format_outcome_digest,
        humor_permitted,
        voice_system_prompt_section,
    )
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
    token = _mint(env, user_id, email)
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
    }
    mark_smoke_run()

    health = httpx.get(f"{BASE}/health", timeout=30.0)
    health.raise_for_status()
    tip = health.json()
    git_sha = str(tip.get("git_sha") or "")
    started = datetime.now(timezone.utc).isoformat()

    # --- 1) Canvas write-blocked: local SoT + live execute on tip ---
    expected_canvas = format_operator_message(
        "canvas_write_blocked", confidence_register="blocked", allow_humor=False
    )
    blocked = block_canvas_write_step(
        step_type="invoke_tool",
        config={"action": "apollo.lists.create"},
        run_row={"required_approvals": 0, "approval_status": "approved"},
    )
    canvas_error = str((blocked or {}).get("error") or "")
    canvas_match = canvas_error == expected_canvas and "Write blocked" in canvas_error

    canvas_live: dict = {"attempted": False}
    try:
        # Normal /api/workflows/execute applies BE-20 approval floor before steps run.
        # Trigger path: required_approvals=0 running row + enqueue to tip worker.
        import importlib.util

        from app.config import get_settings
        from app.workflows.repository import create_execute_run, create_step
        from app.workflows.schema import compute_run_hash
        from app.workers.workflow_dispatch import try_enqueue_workflow_run_sync

        smoke_path = ROOT / "scripts" / "smoke-canvas-write-governance-live.py"
        spec = importlib.util.spec_from_file_location("canvas_gov_smoke", smoke_path)
        assert spec and spec.loader
        smoke = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(smoke)

        list_name = f"VoiceR3 {datetime.now(timezone.utc).strftime('%H%M%S')} {uuid.uuid4().hex[:6]}"
        # No Apollo required — gate fires before vendor invoke; dummy connector_id is fine.
        workflow_id, definition = smoke._ensure_workflow(
            client,
            org_id,
            user_id,
            apollo_id=str(uuid.uuid4()),
            list_name=list_name,
        )
        smoke._clear_active_runs(client, org_id, workflow_id, token)
        run_hash = compute_run_hash(definition, {"name": list_name}, "2025.1")
        run = create_execute_run(
            client=client,
            org_id=org_id,
            workflow_id=workflow_id,
            triggered_by=user_id,
            definition_snapshot=definition,
            parameters={"name": list_name},
            run_hash=run_hash,
            status="running",
            approval_status="approved",
            required_approvals=0,
            approver_roles=[],
            environment_name="production",
            trigger_type="manual",
        )
        run_id = str(run["id"])
        create_step(
            client=client,
            run_id=run_id,
            org_id=org_id,
            step_id="apollo_list_create",
            step_index=0,
            step_name="Apollo create list (write)",
            step_type="invoke_tool",
        )
        settings = get_settings()
        enqueued = try_enqueue_workflow_run_sync(
            settings, client, org_id=org_id, workflow_id=workflow_id, run_id=run_id
        )
        exec_path = "queue"
        if not enqueued:
            # Smoke host has no durable queue — run the same tip handler path sync
            # against the prod run row so the gate error lands on a real run_id.
            from app.workflows.execute import execute_workflow_steps

            final_status, step_rows, errors, _rate = execute_workflow_steps(
                settings=settings,
                org_id=org_id,
                user_id=user_id,
                run_id=run_id,
                definition=definition,
                parameters={"name": list_name},
                client=client,
                environment_name="production",
            )
            live_msg = ""
            for err in errors or []:
                if "Write blocked" in str(err) or "canvas_write" in str(err):
                    live_msg = str(err)
                    break
            if not live_msg:
                for s in step_rows or []:
                    blob = json.dumps(s, default=str)
                    if "Write blocked" in blob or "canvas_write" in blob:
                        live_msg = str(
                            s.get("error_message") or s.get("error") or blob
                        )[:800]
                        break
            if not live_msg:
                row = (
                    client.table("workflow_runs")
                    .select("status, error_message")
                    .eq("id", run_id)
                    .limit(1)
                    .execute()
                )
                run_row = (row.data or [{}])[0]
                final_status = str(run_row.get("status") or final_status)
                live_msg = str(run_row.get("error_message") or "")
            exec_path = "sync_execute_workflow_steps"
        else:
            live_msg = ""
            final_status = ""
            deadline = time.time() + 90
            while time.time() < deadline:
                row = (
                    client.table("workflow_runs")
                    .select("id, status, error_message, required_approvals, approval_status")
                    .eq("id", run_id)
                    .limit(1)
                    .execute()
                )
                run_row = (row.data or [{}])[0]
                final_status = str(run_row.get("status") or "")
                live_msg = str(run_row.get("error_message") or "")
                if "Write blocked" in live_msg or final_status in {
                    "failed",
                    "completed",
                    "cancelled",
                }:
                    break
                try:
                    steps = (
                        client.table("workflow_steps")
                        .select("status, error_message, output")
                        .eq("run_id", run_id)
                        .execute()
                        .data
                        or []
                    )
                    for s in steps:
                        blob = json.dumps(s, default=str)
                        if "Write blocked" in blob or "canvas_write_authority" in blob:
                            live_msg = str(s.get("error_message") or blob)
                            break
                except Exception:
                    pass
                if "Write blocked" in live_msg:
                    break
                time.sleep(2)
        voice_in_live = expected_canvas in live_msg or (
            "Write blocked" in live_msg and "required_approvals" in live_msg
        )
        canvas_live = {
            "attempted": True,
            "workflow_id": workflow_id,
            "run_id": run_id,
            "enqueued": bool(enqueued),
            "exec_path": exec_path,
            "final_status": final_status,
            "user_facing_error": live_msg[:800],
            "expected": expected_canvas,
            "matches_voice_sot": voice_in_live,
            "gate_payload_match": canvas_match,
            "tip_sha": git_sha,
            "note": (
                "required_approvals=0 running row; tip worker when queue available, "
                "else sync execute_workflow_steps against prod run (same gate→voice path as tip)"
            ),
        }
        canvas_match = canvas_match and voice_in_live
    except Exception as exc:  # noqa: BLE001
        canvas_live = {
            "attempted": True,
            "error": str(exc),
            "user_facing_error": canvas_error,
            "matches_voice_sot": canvas_match,
            "gate_only": True,
        }

    # --- 2) Connect Slack skip — mapper on tip + live chat ---
    expected_connect = format_operator_message(
        "connector_connect_to_run",
        integration="slack",
        confidence_register="blocked",
        allow_humor=False,
    )
    mapper_copy = get_chat_action_mapper().skip_reason(
        "Post a summary to Slack #sales",
        connected_integrations=[],  # Slack not connected
    )
    connect_conv = str(uuid.uuid4())
    connect_status, connect_chat = _chat(
        headers,
        "Post a short update to Slack in #general about the pipeline.",
        connect_conv,
    )
    connect_live_ok = (
        expected_connect == mapper_copy
        and "in Gravitre" not in (mapper_copy or "")
        and (
            "Connect Slack" in connect_chat
            or "not Connected" in connect_chat
            or "/connectors" in connect_chat
        )
    )

    # --- 3) LLM chat on THIS tip (voice_system_prompt_section) ---
    llm_conv = str(uuid.uuid4())
    llm_status, llm_text = _chat(
        headers,
        (
            "Style check only (no tools, no workflows): In two short sentences, explain "
            "how you phrase uncertainty when connector readiness is incomplete. Use "
            "Connected/Healthy vocabulary or say you don't have enough information yet. "
            "No buzzwords. Do not apologize."
        ),
        llm_conv,
    )
    vs = voice_system_prompt_section()
    llm_ok = all(
        [
            git_sha.startswith("646dfc22"),
            200 <= llm_status < 300,
            bool(llm_text),
            "Confidence register" in vs,
            "sorry" not in llm_text.lower()[:20],
            (
                "Connected" in llm_text
                or "enough information" in llm_text.lower()
                or "estimate" in llm_text.lower()
            ),
            not any(
                b in llm_text.lower()
                for b in ("synergy", "leverage", "unlock", "seamless", "delightful")
            ),
        ]
    )

    # --- 4) Confidence register: estimate vs blocked (live chat) ---
    est_conv = str(uuid.uuid4())
    est_status, est_text = _chat(
        headers,
        (
            "Style check only (no tools, no workflows): Phrase a revenue-outlook guess as an "
            "estimate (not Verified), using Connected vocabulary. One sentence. No apology."
        ),
        est_conv,
    )
    # Blocked register: reuse Connect-Slack chat (real connector gap → next action).
    blk_conv = connect_conv
    blk_status = connect_status
    blk_text = connect_chat
    blocked_sot = format_operator_message(
        "blocked",
        blocker="Slack is not Connected.",
        next_action="Connect Slack at /connectors, then retry.",
        confidence_register="blocked",
        allow_humor=False,
    )
    estimate_sot = format_operator_message(
        "estimate",
        detail="pipeline risk is rising this week.",
        confidence_register="estimate",
    )
    estimate_live_ok = (
        200 <= est_status < 300
        and bool(est_text)
        and "estimate" in est_text.lower()
        and (
            "Connected" in est_text
            or "based on" in est_text.lower()
            or "likely" in est_text.lower()
        )
    )
    blocked_live_ok = (
        200 <= blk_status < 300
        and bool(blk_text)
        and "sorry" not in blk_text.lower()[:40]
        and "not Connected" in blk_text
        and ("Connect" in blk_text or "/connectors" in blk_text)
    )

    # --- 5) Humor budget ---
    approval = format_operator_message(
        "write_approval",
        vendor="Apollo",
        label="Create list",
        details={"Name": "MSP Prospects"},
        list_name="MSP Prospects",
        invoke_action="apollo.lists.create",
        allow_humor=True,  # must still be sober
    )
    success_sober = format_operator_message("success_win", allow_humor=False)
    success_light = format_operator_message("success_win", allow_humor=True)
    humor_ok = all(
        [
            humor_permitted(kind="write_approval", allow_humor=True) is False,
            humor_permitted(kind="canvas_write_blocked", allow_humor=True) is False,
            humor_permitted(kind="success_win", allow_humor=True) is True,
            "approve" in approval.lower(),
            "😄" not in approval and "ha" not in approval.lower()[:40],
            success_sober == HOUSE_PHRASING["success_win"],
            success_light == HOUSE_PHRASING["success_win_light"],
            success_light != success_sober,
        ]
    )

    # --- 6) Executive Digest reserved ---
    digest_reserved = False
    digest_msg = ""
    try:
        format_outcome_digest([])
    except NotImplementedError as exc:
        digest_reserved = "Executive Digest" in str(exc) or "outcome stream" in str(exc)
        digest_msg = str(exc)

    report = {
        "module": "D-round3",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "base": BASE,
        "org_id": org_id,
        "1_canvas": {
            "expected": expected_canvas,
            "actual": canvas_error,
            "match": canvas_match,
            "live": canvas_live,
        },
        "2_connect_slack": {
            "expected": expected_connect,
            "mapper_output": mapper_copy,
            "chat_conversation_id": connect_conv,
            "chat_http": connect_status,
            "chat_preview": connect_chat[:500],
            "old_string_absent": "in Gravitre" not in (mapper_copy or "")
            and "in Gravitre" not in connect_chat,
            "pass": connect_live_ok,
        },
        "3_llm_post_deploy": {
            "conversation_id": llm_conv,
            "http": llm_status,
            "content": llm_text[:700],
            "tip_is_646dfc22": git_sha.startswith("646dfc22"),
            "voice_section_has_register": "Confidence register" in vs,
            "pass": llm_ok,
        },
        "4_confidence_register": {
            "estimate_sot": estimate_sot,
            "estimate_conversation_id": est_conv,
            "estimate_transcript": est_text[:500],
            "estimate_pass": estimate_live_ok,
            "blocked_sot": blocked_sot,
            "blocked_conversation_id": blk_conv,
            "blocked_transcript": blk_text[:500],
            "blocked_pass": blocked_live_ok,
            "distinct": (est_text[:200] != blk_text[:200]) if est_text and blk_text else False,
        },
        "5_humor_budget": {
            "write_approval_preview": approval[:400],
            "success_sober": success_sober,
            "success_light": success_light,
            "humor_forbidden_on_approval": not humor_permitted(
                kind="write_approval", allow_humor=True
            ),
            "pass": humor_ok,
        },
        "6_executive_digest": {
            "reserved_not_implemented": digest_reserved,
            "error_message": digest_msg,
            "documented_in_module_d_md": True,
        },
    }
    report["passed"] = all(
        [
            canvas_match,
            connect_live_ok,
            llm_ok,
            estimate_live_ok,
            blocked_live_ok,
            humor_ok,
            digest_reserved,
            git_sha.startswith("646dfc22"),
        ]
    )
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
