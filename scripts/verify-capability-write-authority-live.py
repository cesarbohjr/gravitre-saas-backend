#!/usr/bin/env python3
"""Live proof: capability-resolved CRM write uses the same write gate as direct HubSpot.

Exercises deployed code via ReActEngine._execute_tool_call (same path as
smoke-react-write-live.py / smoke-multi-provider-tool-live.py):

  direct hubspot_contacts_create → write_approval_required @ hubspot.contacts.create
  capability__crm__contact__create (HubSpot connected) → same error_code + action

Writes docs/delivery/capability-write-authority-live.json with git_sha from /health.

Usage:
  python scripts/verify-capability-write-authority-live.py
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

import httpx  # noqa: E402
import subprocess  # noqa: E402
from dotenv import dotenv_values  # noqa: E402


BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "capability-write-authority-live.json"


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


def _local_git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            text=True,
            timeout=10,
        ).strip()
        return out or None
    except Exception:  # noqa: BLE001
        return None


def _health() -> dict:
    try:
        return httpx.get(f"{BASE}/health", timeout=60.0).json()
    except Exception as exc:  # noqa: BLE001
        return {"git_sha": None, "error": f"{exc.__class__.__name__}:{exc}"}


async def _probe_write_gate(
    *,
    org_id: str,
    actor_id: str,
    tool_name: str,
    args: dict,
) -> dict:
    from app.config import get_settings
    from app.operators.react_engine import ReActEngine
    from app.services.react_write_gate import WRITE_APPROVAL_REQUIRED
    from app.services.tool_registry import get_tool_registry
    from app.services.tool_types import ToolContext
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
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
    started = datetime.now(timezone.utc)
    blocked = await engine._execute_tool_call(
        ctx,
        tool_name,
        args,
        allowed_tool_names={tool_name},
    )
    finished = datetime.now(timezone.utc)
    return {
        "at": finished.isoformat(),
        "latency_ms": int((finished - started).total_seconds() * 1000),
        "tool": tool_name,
        "success": blocked.get("success"),
        "error_code": blocked.get("error_code"),
        "pending_approval": blocked.get("pending_approval"),
        "action": blocked.get("action"),
        "integration": blocked.get("integration"),
        "label": blocked.get("label"),
        "pass": (
            blocked.get("error_code") == WRITE_APPROVAL_REQUIRED
            and blocked.get("pending_approval") is True
            and blocked.get("action") == "hubspot.contacts.create"
        ),
    }


async def _run(*, org_id: str, actor_id: str) -> dict:
    from app.capability_ontology.tool_bridge import capability_tool_name
    from app.config import get_settings
    from app.services.tool_registry import get_tool_registry
    from app.workflows.repository import get_supabase_client

    health = _health()
    settings = get_settings()
    client = get_supabase_client(settings)
    reg = get_tool_registry()
    connected = reg.list_connected_integrations(
        client,
        org_id,
        environment_name=os.environ.get("OAUTH_SMOKE_ENVIRONMENT", "production"),
    )

    cap_tool = capability_tool_name("crm.contact.create")
    args = {"email": f"cap-write-gate-{uuid.uuid4().hex[:8]}@example.com"}

    direct = await _probe_write_gate(
        org_id=org_id,
        actor_id=actor_id,
        tool_name="hubspot_contacts_create",
        args=args,
    )
    capability = await _probe_write_gate(
        org_id=org_id,
        actor_id=actor_id,
        tool_name=cap_tool,
        args={**args, "preferred_vendor": "hubspot"},
    )

    parity = (
        direct.get("pass")
        and capability.get("pass")
        and direct.get("error_code") == capability.get("error_code") == "write_approval_required"
        and direct.get("action") == capability.get("action") == "hubspot.contacts.create"
    )

    local_sha = _local_git_sha()
    deployed_sha = str(health.get("git_sha") or "")
    sha_match = bool(local_sha and deployed_sha and local_sha.startswith(deployed_sha[:12]))
    require_sha = os.environ.get("CAPABILITY_LIVE_REQUIRE_SHA_MATCH", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }

    return {
        "probe_started_at": datetime.now(timezone.utc).isoformat(),
        "backend_url": BASE,
        "health": health,
        "git_sha": deployed_sha or None,
        "local_git_sha": local_sha,
        "deploy_sha_match": sha_match,
        "require_deploy_sha_match": require_sha,
        "org_id": org_id,
        "actor_id": actor_id,
        "connected_integrations": connected,
        "path": "react_write_gate direct vs capability-resolved (HubSpot CRM contact create)",
        "direct_hubspot_tool": direct,
        "capability_resolved_tool": capability,
        "parity": {
            "same_error_code": direct.get("error_code") == capability.get("error_code"),
            "same_invoke_action": direct.get("action") == capability.get("action"),
            "both_pending_approval": bool(
                direct.get("pending_approval") and capability.get("pending_approval")
            ),
            "pass": parity,
        },
        "pass": parity and (sha_match or not require_sha),
        "claim": (
            "PASS — write_approval_required hubspot.contacts.create @ capability parity (deployed tip)"
            if parity and sha_match
            else (
                "PARTIAL — gate parity OK locally but deployed git_sha != local commit"
                if parity and require_sha and not sha_match
                else "FAIL — capability write gate did not match direct HubSpot gate"
            )
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Live capability vs direct write-authority parity")
    parser.add_argument("--json", dest="json_path", default=str(OUT))
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

    print("PROBE_START", datetime.now(timezone.utc).isoformat())
    print("BACKEND", BASE)
    print("ORG", org_id)
    print("ACTOR", actor_id)

    report = asyncio.run(_run(org_id=org_id, actor_id=actor_id))
    json_path = Path(args.json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("WROTE", json_path)
    print("GIT_SHA", report.get("git_sha"))
    print("CLAIM", report.get("claim"))
    print(
        "PARITY",
        json.dumps(report.get("parity") or {}, indent=2),
    )

    if not report.get("pass"):
        if (report.get("parity") or {}).get("pass") and not report.get("deploy_sha_match"):
            print("PARTIAL gate parity OK — waiting for deploy SHA match")
        return 1
    print("PASS capability write-authority parity on deployed tip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
