#!/usr/bin/env python3
"""Live ReAct write → approval → execute_plan smoke (Wave 0–2 permanent regression).

Distinct from smoke-oauth-live.py (governed invoke_tool path). This exercises:
  ReActEngine._execute_tool_call (synthetic agent) → write_approval_required
  → plan_from_react_write → ChatConnectorExecutionService.execute_plan
  → tool.invoke.completed

Cadence: connector-verified-writes-live.yml (daily + workflow_dispatch).

Usage:
  python scripts/smoke-react-write-live.py
  python scripts/smoke-react-write-live.py --json docs/delivery/react-write-live-latest.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import dotenv_values  # noqa: E402


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip('"')
                if value:
                    merged[key.strip()] = value
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _resolve_actor(client, org_id: str, env: dict[str, str]) -> str:
    actor = (env.get("OAUTH_SMOKE_USER_ID") or env.get("SMOKE_USER_ID") or "").strip()
    if actor:
        return actor
    rows = client.table("organization_members").select("user_id").eq("org_id", org_id).limit(1).execute()
    actor = str((rows.data or [{}])[0].get("user_id") or "")
    if not actor:
        raise SystemExit("Set OAUTH_SMOKE_USER_ID or ensure organization_members has a row")
    return actor


async def _run(*, org_id: str, actor_id: str, list_name: str, json_path: Path) -> dict:
    from app.config import get_settings
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
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    conv = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    evidence: dict = {
        "probe_started_at": started,
        "list_name": list_name,
        "org_id": org_id,
        "conversation_id": conv,
        "actor_id": actor_id,
        "path": "react_write_gate -> awaiting_confirm -> execute_plan",
        "agent_id": "synthetic-default",
    }

    reg = get_tool_registry()
    engine = ReActEngine(settings=settings, registry=reg)
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        agent_id="synthetic-default",
        environment_name=os.environ.get("OAUTH_SMOKE_ENVIRONMENT", "production"),
    )

    t0 = datetime.now(timezone.utc)
    blocked = await engine._execute_tool_call(
        ctx,
        "apollo_lists_create",
        {"name": list_name, "modality": "contacts"},
        allowed_tool_names={"apollo_lists_create"},
    )
    t1 = datetime.now(timezone.utc)
    evidence["react_gate"] = {
        "at": t1.isoformat(),
        "latency_ms": int((t1 - t0).total_seconds() * 1000),
        "success": blocked.get("success"),
        "error_code": blocked.get("error_code"),
        "pending_approval": blocked.get("pending_approval"),
        "action": blocked.get("action"),
        "tool": blocked.get("tool"),
    }
    print("REACT_GATE", json.dumps(evidence["react_gate"], indent=2))
    if blocked.get("error_code") != WRITE_APPROVAL_REQUIRED:
        evidence["failed_at"] = "react_gate"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        raise SystemExit(f"unexpected gate result: {blocked}")

    react_result = ReActResult(
        status=ReActStatus.NEEDS_HUMAN_INPUT,
        answer="Write requires approval",
        tool_calls=[
            {
                "tool": "apollo_lists_create",
                "name": "apollo_lists_create",
                "args": {"name": list_name, "modality": "contacts"},
                "result": blocked,
            }
        ],
    )
    pending = pending_write_from_react(react_result)
    plan = plan_from_react_write(pending, reg)
    if plan is None:
        evidence["failed_at"] = "plan_from_react_write"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        raise SystemExit("plan_from_react_write returned None")

    evidence["approval_plan"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "invoke_action": plan.invoke_action,
        "requires_approval": getattr(plan, "requires_approval", None),
        "label": getattr(plan, "label", None),
        "args": getattr(plan, "args", None),
        "source": "react_write_gate",
        "dialogue_mode": "confirm",
        "ci_auto_approve": True,
    }
    print("APPROVAL_PLAN", json.dumps(evidence["approval_plan"], indent=2, default=str))

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
    evidence["pending_persisted_at"] = datetime.now(timezone.utc).isoformat()
    evidence["user_approval_at"] = datetime.now(timezone.utc).isoformat()

    svc = get_chat_connector_execution_service(settings)
    t2 = datetime.now(timezone.utc)
    result = await svc.execute_plan(
        org_id=org_id,
        user_id=actor_id,
        conversation_id=conv,
        plan=plan,
        client=client,
        classification={"intent": "connector_action", "requires_approval": True},
        environment_name=os.environ.get("OAUTH_SMOKE_ENVIRONMENT", "production"),
    )
    t3 = datetime.now(timezone.utc)
    evidence["execution"] = {
        "at": t3.isoformat(),
        "latency_ms": int((t3 - t2).total_seconds() * 1000),
        "success": result.success,
        "error_code": result.error_code,
        "entity_id": result.entity_id,
        "result_url": result.result_url,
        "body": (result.body or "")[:400],
        "integration": result.integration,
        "task_label": result.task_label,
    }
    print("EXECUTION", json.dumps(evidence["execution"], indent=2))
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("WROTE", json_path)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Live ReAct write→approval→execute smoke")
    parser.add_argument(
        "--json",
        dest="json_path",
        default=str(REPO / "docs" / "delivery" / "react-write-live-latest.json"),
        help="Evidence JSON output path",
    )
    parser.add_argument(
        "--list-name",
        default=None,
        help="Apollo list name (default: gravitre-react-gate-probe-YYYYMMDD)",
    )
    args = parser.parse_args()

    env = _load_env()
    for key, value in env.items():
        os.environ.setdefault(key, value)

    from app.config import get_settings
    from app.workflows.repository import get_supabase_client
    from isolated_conversation_org import resolve_isolated_conversation_actor

    settings = get_settings()
    client = get_supabase_client(settings)
    org_id, actor_id, _email = resolve_isolated_conversation_actor(env, client)
    list_name = args.list_name or (
        f"gravitre-react-gate-probe-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    )
    json_path = Path(args.json_path)

    print("PROBE_START", datetime.now(timezone.utc).isoformat())
    print("LIST_NAME", list_name)
    print("ORG", org_id)
    print("ACTOR", actor_id)

    evidence = asyncio.run(
        _run(org_id=org_id, actor_id=actor_id, list_name=list_name, json_path=json_path)
    )
    execution = evidence.get("execution") or {}
    if not execution.get("success"):
        code = execution.get("error_code") or "execution_failed"
        print(f"FAIL error_code={code}")
        return 1
    print("PASS react write chain completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
