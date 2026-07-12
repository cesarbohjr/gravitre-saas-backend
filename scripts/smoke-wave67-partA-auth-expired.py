#!/usr/bin/env python3
"""Part A — connected-but-expired Slack → mid-stream ToolChip with auth_expired.

Prereq: Slack connector row status temporarily healthy while OAuth token remains expired.
Restores status=error in finally.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
import sys

sys.path.insert(0, str(BACKEND))

for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
    if p.is_file():
        for k, v in dotenv_values(p).items():
            if v:
                os.environ.setdefault(k, v)

from app.config import get_settings  # noqa: E402
from app.operators.assistant_sse import format_react_tool_output, sse_react_tool_complete  # noqa: E402
from app.operators.react_engine import ReActEngine, ReActResult, ReActStatus  # noqa: E402
from app.services.chat_connector_execution_service import (  # noqa: E402
    ChatConnectorExecutionService,
    get_chat_connector_execution_service,
)
from app.services.conversation_state_service import get_conversation_state_service  # noqa: E402
from app.services.react_write_gate import (  # noqa: E402
    WRITE_APPROVAL_REQUIRED,
    plan_from_react_write,
    pending_write_from_react,
)
from app.services.tool_registry import get_tool_registry  # noqa: E402
from app.services.tool_types import ToolContext  # noqa: E402
from app.workflows.repository import get_supabase_client  # noqa: E402

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
SLACK_ID = "fe7433c3-6475-474a-863f-91b98d17a0b8"


async def main() -> None:
    settings = get_settings()
    client = get_supabase_client(settings)
    actor = str(
        (client.table("organization_members").select("user_id").eq("org_id", ORG).limit(1).execute().data or [{}])[
            0
        ].get("user_id")
        or ""
    )
    reg = get_tool_registry()
    engine = ReActEngine(settings=settings, registry=reg)
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=ORG,
        actor_id=actor,
        agent_id="synthetic-default",
        environment_name="production",
        connector_id=SLACK_ID,
    )
    evidence: dict = {
        "part": "A",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "setup": {
            "slack_connector_id": SLACK_ID,
            "note": "status temporarily healthy; token remains expired (connected-but-broken)",
        },
        "events": [],
    }

    try:
        # --- Mid-stream READ path: no write gate; should hit vendor auth_expired ---
        t0 = datetime.now(timezone.utc).isoformat()
        read_obs = await engine._execute_tool_call(
            ctx,
            "slack_conversations_list",
            {"limit": 5},
            allowed_tool_names={"slack_conversations_list"},
        )
        t1 = datetime.now(timezone.utc).isoformat()
        shaped_read = format_react_tool_output("slack_conversations_list", read_obs)
        chip = sse_react_tool_complete(
            call_id=f"call-{uuid.uuid4().hex[:8]}",
            registry_tool_name="slack_conversations_list",
            observation=read_obs,
        )
        evidence["events"].append(
            {
                "step": "midstream_read_tool",
                "started_at": t0,
                "ended_at": t1,
                "observation": {
                    "success": read_obs.get("success"),
                    "error_code": read_obs.get("error_code"),
                    "error": str(read_obs.get("error") or "")[:240],
                    "action": read_obs.get("action"),
                },
                "shaped_chip": shaped_read,
                "sse_tool_output_type": chip.sse_type,
                "sse_errorCode": (chip.payload.get("output") or {}).get("errorCode"),
            }
        )
        print("READ", json.dumps(evidence["events"][-1], indent=2))

        # --- WRITE path: approval gate then execute_plan → vendor auth failure ---
        blocked = await engine._execute_tool_call(
            ctx,
            "slack_post_message",
            {
                "channel": os.environ.get("OAUTH_SMOKE_SLACK_CHANNEL") or "#general",
                "text": "gravitre-wave67-partA auth_expired probe — ignore",
            },
            allowed_tool_names={"slack_post_message"},
        )
        gate_at = datetime.now(timezone.utc).isoformat()
        evidence["events"].append(
            {
                "step": "write_gate",
                "at": gate_at,
                "error_code": blocked.get("error_code"),
                "pending_approval": blocked.get("pending_approval"),
            }
        )
        print("GATE", blocked.get("error_code"))

        if blocked.get("error_code") == WRITE_APPROVAL_REQUIRED:
            conv = str(uuid.uuid4())
            react = ReActResult(
                status=ReActStatus.NEEDS_HUMAN_INPUT,
                answer="need approval",
                tool_calls=[
                    {
                        "tool": "slack_post_message",
                        "args": {
                            "channel": os.environ.get("OAUTH_SMOKE_SLACK_CHANNEL") or "#general",
                            "text": "gravitre-wave67-partA auth_expired probe — ignore",
                        },
                        "result": blocked,
                    }
                ],
            )
            plan = plan_from_react_write(pending_write_from_react(react), reg)
            # Ensure invoke can resolve the expired-but-present connector by id
            if plan is not None:
                args = dict(plan.args or {})
                args["connector_id"] = SLACK_ID
                from dataclasses import replace

                plan = replace(plan, args=args)
            state = get_conversation_state_service(settings)
            await state.update_task_state(
                conv,
                ORG,
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
            result = await get_chat_connector_execution_service(settings).execute_plan(
                org_id=ORG,
                user_id=actor,
                conversation_id=conv,
                plan=plan,
                client=client,
                classification={"intent": "connector_action", "requires_approval": True},
                environment_name="production",
            )
            done_at = datetime.now(timezone.utc).isoformat()
            fail_obs = {
                "success": False,
                "error_code": result.error_code,
                "error": result.body,
                "integration": "slack",
                "action": "slack.post_message",
            }
            shaped_write = format_react_tool_output("slack_post_message", fail_obs)
            evidence["events"].append(
                {
                    "step": "write_after_approve",
                    "conversation_id": conv,
                    "approve_at": approve_at,
                    "done_at": done_at,
                    "execution": {
                        "success": result.success,
                        "error_code": result.error_code,
                        "body": (result.body or "")[:300],
                        "entity_id": result.entity_id,
                    },
                    "shaped_chip": shaped_write,
                }
            )
            print("WRITE", json.dumps(evidence["events"][-1], indent=2))

        # Claim scoring
        read_code = (evidence["events"][0].get("observation") or {}).get("error_code")
        read_chip = evidence["events"][0].get("sse_errorCode")
        write_ev = next((e for e in evidence["events"] if e.get("step") == "write_after_approve"), None)
        write_code = (write_ev or {}).get("execution", {}).get("error_code") if write_ev else None
        write_chip = ((write_ev or {}).get("shaped_chip") or {}).get("errorCode")

        claim2 = {
            "status": "PASS"
            if read_code == "auth_expired" and read_chip == "auth_expired"
            else ("PARTIAL" if read_code == "auth_expired" or write_code == "auth_expired" else "FAIL"),
            "required_mode": "connected_but_expired → auth_expired (not tool_not_available)",
            "read_midstream": {"error_code": read_code, "chip_errorCode": read_chip},
            "write_chain": {
                "gate": WRITE_APPROVAL_REQUIRED,
                "execution_error_code": write_code,
                "chip_errorCode": write_chip,
            },
        }
        if read_code == "tool_not_available":
            claim2["status"] = "FAIL"
            claim2["note"] = "Got disconnected-path code; Part A requires auth_expired"
        evidence["claim_2"] = claim2
    finally:
        client.table("connectors").update({"status": "error"}).eq("id", SLACK_ID).eq("org_id", ORG).execute()
        evidence["restored_status"] = "error"
        evidence["finished_at"] = datetime.now(timezone.utc).isoformat()

    out = REPO / "docs" / "delivery" / "wave67-partA-auth-expired.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("CLAIM2", json.dumps(evidence.get("claim_2"), indent=2))
    print("WROTE", out)


if __name__ == "__main__":
    asyncio.run(main())
