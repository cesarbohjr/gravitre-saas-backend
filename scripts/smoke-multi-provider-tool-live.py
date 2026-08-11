#!/usr/bin/env python3
"""Live multi-provider tool-calling + unified MCP write-gate smoke.

Closes Catalog Portability audit evidence:
  - READ via native Anthropic / Gemini tool APIs (OpenAI tool path guarded)
  - WRITE approval gate per provider agent configuration
  - Destructive mcp_* tool blocked by react_write_gate (not keyword bypass)

Usage:
  python scripts/smoke-multi-provider-tool-live.py
  python scripts/smoke-multi-provider-tool-live.py --json docs/delivery/multi-provider-tool-live-latest.json

Requires prod credentials in backend/.env.operator.local (ANTHROPIC_API_KEY,
GEMINI_API_KEY, OPENAI_API_KEY, Supabase service role).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import dotenv_values  # noqa: E402

MIN_SHA_PREFIX = "fe952caf"
OUT_DEFAULT = REPO / "docs" / "delivery" / "multi-provider-tool-live-latest.json"
PROD_HEALTH = "https://api.gravitre.app/health"

# Stable smoke agent ids in the isolated conversation org.
CLAUDE_AGENT_ID = "a1111111-1111-4111-8111-111111110001"
GEMINI_AGENT_ID = "a1111111-1111-4111-8111-111111110002"

_GEMINI_ENV = os.environ.get("SMOKE_GEMINI_MODEL", "").strip()
GEMINI_MODEL_FALLBACKS: tuple[str, ...] = (
    (_GEMINI_ENV,) if _GEMINI_ENV else ()
) + (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-2.0-flash",
)

PROVIDER_MATRIX: list[tuple[str, str, str]] = [
    ("anthropic", "claude-sonnet-4-6", CLAUDE_AGENT_ID),
    ("gemini", GEMINI_MODEL_FALLBACKS[0], GEMINI_AGENT_ID),
]

READ_TOOL = "assistant_connector_status"
WRITE_TOOL = "apollo_lists_create"
MCP_WRITE_TOOL = "mcp_smoke_probe_delete_record"
SMOKE_HITL_POLICY_ID = "b1111111-1111-4111-8111-111111110001"


class OpenAIToolPathForbidden(RuntimeError):
    """Raised when OpenAI chat.completions.create(tools=) is invoked during a non-OpenAI probe."""


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


def _sha_at_least(deployed: str, minimum: str) -> bool:
    d = str(deployed or "").strip().lower()
    m = str(minimum or "").strip().lower()
    if not d or not m:
        return False
    if d.startswith(m) or m.startswith(d[: len(m)]):
        return True
    try:
        import subprocess

        proc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", m, d],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _health() -> dict[str, Any]:
    import urllib.request

    with urllib.request.urlopen(PROD_HEALTH, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ensure_smoke_hitl_write_policy(client: Any, org_id: str, actor_id: str) -> dict[str, Any]:
    """Org-scoped write/delete approval so react_write_gate blocks during smoke."""
    row = {
        "id": SMOKE_HITL_POLICY_ID,
        "org_id": org_id,
        "name": "Smoke multi-provider write gate",
        "enabled": True,
        "scope_type": "org",
        "action_kinds": ["write", "delete"],
        "approver_roles": ["admin", "owner"],
        "approver_user_ids": [],
        "required_approvals": 1,
        "created_by": actor_id,
    }
    existing = (
        client.table("hitl_policies")
        .select("id")
        .eq("id", SMOKE_HITL_POLICY_ID)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        client.table("hitl_policies").update(
            {
                "name": row["name"],
                "enabled": True,
                "action_kinds": row["action_kinds"],
                "approver_roles": row["approver_roles"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", SMOKE_HITL_POLICY_ID).eq("org_id", org_id).execute()
    else:
        client.table("hitl_policies").insert(row).execute()
    return row


def _upsert_smoke_agent(client: Any, org_id: str, agent_id: str, name: str, model: str) -> dict[str, Any]:
    row = {
        "id": agent_id,
        "org_id": org_id,
        "name": name,
        "purpose": "Multi-provider native tool-calling smoke probe",
        "role": "operator",
        "model": model,
        "systems": ["platform", "apollo"],
        "status": "active",
        "config": {
            "smoke_probe": True,
            "permitted_tools": ["*"],
            "description": "Ephemeral smoke agent — do not use in customer workflows",
        },
    }
    existing = (
        client.table("agents")
        .select("id")
        .eq("id", agent_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        client.table("agents").update(
            {
                "name": row["name"],
                "model": row["model"],
                "systems": row["systems"],
                "status": row["status"],
                "config": row["config"],
                "purpose": row["purpose"],
            }
        ).eq("id", agent_id).eq("org_id", org_id).execute()
    else:
        client.table("agents").insert(row).execute()
    return row


def _fetch_inference_audits(
    client: Any,
    *,
    org_id: str,
    resource_id: str,
    since_iso: str,
) -> list[dict[str, Any]]:
    resp = (
        client.table("audit_events")
        .select("id,action,metadata,created_at,resource_id")
        .eq("org_id", org_id)
        .eq("action", "inference.tool_completion")
        .eq("resource_id", resource_id)
        .gte("created_at", since_iso)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return list(resp.data or [])


@asynccontextmanager
async def _openai_tool_guard(router: Any, *, forbid: bool):
    """Block OpenAI chat.completions.create(tools=...) when probing non-OpenAI providers."""
    if not forbid:
        yield
        return
    client = getattr(router, "_openai", None)
    if client is None:
        yield
        return
    original = client.chat.completions.create

    async def _guarded(**kwargs: Any) -> Any:
        if kwargs.get("tools"):
            raise OpenAIToolPathForbidden(
                "REGRESSION: OpenAI chat.completions.create(tools=...) invoked for non-OpenAI agent"
            )
        return await original(**kwargs)

    client.chat.completions.create = _guarded
    try:
        yield
    finally:
        client.chat.completions.create = original


async def _probe_read(
    *,
    engine: Any,
    ctx: Any,
    agent: dict[str, Any],
    model: str,
    provider: str,
    probe_id: str,
    client: Any,
    org_id: str,
    started_iso: str,
) -> dict[str, Any]:
    from app.services.agent_platform_optimizer import narrow_tools_for_turn
    from app.services.narrowed_tools import mark_narrowed
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    all_tools = registry.get_tools_for_agent(["*"], ["platform", "apollo"])
    narrowed, stats = narrow_tools_for_turn(
        all_tools,
        query="connector status integrations connected",
        connected_integrations=["platform", "apollo"],
        max_tools=28,
    )
    read_tools = mark_narrowed(
        [t for t in narrowed if (t.get("function") or {}).get("name") == READ_TOOL],
        stats=stats,
        source="smoke_multi_provider_read",
    )
    if not read_tools:
        read_tools = mark_narrowed(
            [t for t in all_tools if (t.get("function") or {}).get("name") == READ_TOOL][:1],
            source="smoke_multi_provider_read_fallback",
        )

    task = (
        "Call assistant_connector_status once to list connected integrations for this org. "
        "Do not guess — you must invoke the tool."
    )
    forbid_openai = provider != "openai"
    async with _openai_tool_guard(engine.router, forbid=forbid_openai):
        result = await engine.run(
            ctx=ctx,
            task=task,
            system_prompt="You are a smoke probe agent. Always call the requested tool.",
            agent=agent,
            model=model,
            connected_integrations=["platform", "apollo"],
            permitted_tools=["*"],
            max_iterations=4,
            audit_resource_type="agent_job",
            audit_resource_id=probe_id,
        )

    audits = _fetch_inference_audits(client, org_id=org_id, resource_id=probe_id, since_iso=started_iso)
    provider_audits = [
        a
        for a in audits
        if str((a.get("metadata") or {}).get("provider") or "") == provider
        and str((a.get("metadata") or {}).get("model") or "") == model
    ]
    tool_names = [str(c.get("tool") or "") for c in (result.tool_calls or [])]
    read_called = READ_TOOL in tool_names
    read_success = any(
        isinstance(c.get("result"), dict) and c.get("result", {}).get("success") is True
        for c in (result.tool_calls or [])
        if str(c.get("tool") or "") == READ_TOOL
    )

    return {
        "probe_id": probe_id,
        "provider": provider,
        "model": model,
        "openai_tool_path_forbidden": forbid_openai,
        "react_status": str(getattr(result.status, "value", result.status)),
        "tool_calls": result.tool_calls,
        "read_tool_called": read_called,
        "read_tool_success": read_success,
        "inference_audit_rows": provider_audits,
        "pass": bool(read_called and read_success and provider_audits),
    }


async def _probe_write(
    *,
    engine: Any,
    ctx: Any,
    provider: str,
    model: str,
    list_name: str,
) -> dict[str, Any]:
    from app.services.react_write_gate import WRITE_APPROVAL_REQUIRED

    blocked = await engine._execute_tool_call(
        ctx,
        WRITE_TOOL,
        {"name": list_name, "modality": "contacts"},
        allowed_tool_names={WRITE_TOOL},
    )
    return {
        "provider": provider,
        "model": model,
        "tool": WRITE_TOOL,
        "list_name": list_name,
        "success": blocked.get("success"),
        "error_code": blocked.get("error_code"),
        "pending_approval": blocked.get("pending_approval"),
        "action": blocked.get("action"),
        "pass": blocked.get("error_code") == WRITE_APPROVAL_REQUIRED and blocked.get("pending_approval") is True,
        "note": (
            "Write gate is provider-agnostic at execution; READ probe proves native inference routing."
        ),
    }


async def _probe_mcp_write(*, engine: Any, ctx: Any, registry: Any) -> dict[str, Any]:
    from app.services.react_write_gate import WRITE_APPROVAL_REQUIRED, tool_requires_user_write_approval

    registry._mcp_meta[MCP_WRITE_TOOL] = {
        "capability_tier": "write",
        "requires_approval": True,
        "read_only_hint": False,
        "destructive_hint": True,
        "label": "Smoke destructive MCP delete",
        "description": "Smoke probe — destructive MCP write classification",
    }
    requires, invoke_action, integration, label = tool_requires_user_write_approval(MCP_WRITE_TOOL, registry)
    blocked = await engine._execute_tool_call(
        ctx,
        MCP_WRITE_TOOL,
        {"record_id": "smoke-1"},
        allowed_tool_names={MCP_WRITE_TOOL},
    )
    return {
        "tool": MCP_WRITE_TOOL,
        "classified_requires_write": requires,
        "invoke_action": invoke_action,
        "integration": integration,
        "label": label,
        "success": blocked.get("success"),
        "error_code": blocked.get("error_code"),
        "pending_approval": blocked.get("pending_approval"),
        "pass": (
            requires is True
            and blocked.get("error_code") == WRITE_APPROVAL_REQUIRED
            and blocked.get("pending_approval") is True
        ),
    }


async def _run_smoke(*, json_path: Path) -> dict[str, Any]:
    from app.config import get_settings
    from app.operators.react_engine import ReActEngine
    from app.services.providers.provider_tool_router import provider_tools_configured
    from app.services.tool_registry import get_tool_registry
    from app.services.tool_types import ToolContext
    from app.workflows.repository import get_supabase_client
    from isolated_conversation_org import mark_smoke_run, resolve_isolated_conversation_actor

    mark_smoke_run()
    env = _load_env()
    for key, value in env.items():
        os.environ.setdefault(key, value)

    settings = get_settings()
    client = get_supabase_client(settings)
    org_id, actor_id, _email = resolve_isolated_conversation_actor(env, client)

    health = _health()
    git_sha = str(health.get("git_sha") or "")
    started = datetime.now(timezone.utc)
    started_iso = started.isoformat()
    nonce = started.strftime("%Y%m%d%H%M%S")

    report: dict[str, Any] = {
        "probe": "multi_provider_tool_live",
        "started_at": started_iso,
        "org_id": org_id,
        "actor_id": actor_id,
        "health": health,
        "min_sha_prefix": MIN_SHA_PREFIX,
        "deploy_sha_ok": _sha_at_least(git_sha, MIN_SHA_PREFIX),
        "api_keys": {},
        "agents": {},
        "providers": {},
        "mcp_unified_gate": {},
        "pass": False,
    }

    for provider in ("openai", "anthropic", "gemini"):
        report["api_keys"][provider] = provider_tools_configured(provider, settings)

    missing = [p for p in ("anthropic", "gemini") if not report["api_keys"].get(p)]
    if missing:
        report["failed_at"] = "missing_api_keys"
        report["missing_providers"] = missing
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    if not report["deploy_sha_ok"]:
        report["failed_at"] = "deploy_sha_below_minimum"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    registry = get_tool_registry()
    engine = ReActEngine(settings=settings, registry=registry)
    hitl_policy = _ensure_smoke_hitl_write_policy(client, org_id, actor_id)
    report["hitl_policy"] = {"id": SMOKE_HITL_POLICY_ID, "name": hitl_policy.get("name")}
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        agent_id="multi-provider-smoke",
        environment_name=os.environ.get("OAUTH_SMOKE_ENVIRONMENT", "production"),
    )

    for provider, model, agent_id in PROVIDER_MATRIX:
        agent_row = _upsert_smoke_agent(
            client,
            org_id,
            agent_id,
            name=f"Smoke {provider} tool probe",
            model=model,
        )
        report["agents"][provider] = {"id": agent_id, "model": model, "row": agent_row}
        agent = dict(agent_row)
        probe_id = str(uuid.uuid4())
        list_name = f"gravitre-provider-smoke-{provider}-{nonce}"

        read_evidence = await _probe_read(
            engine=engine,
            ctx=ctx,
            agent=agent,
            model=model,
            provider=provider,
            probe_id=probe_id,
            client=client,
            org_id=org_id,
            started_iso=started_iso,
        )
        write_evidence = await _probe_write(
            engine=engine,
            ctx=ctx,
            provider=provider,
            model=model,
            list_name=list_name,
        )
        report["providers"][provider] = {
            "model": model,
            "agent_id": agent_id,
            "read": read_evidence,
            "write": write_evidence,
            "pass": bool(read_evidence.get("pass") and write_evidence.get("pass")),
        }

    report["mcp_unified_gate"] = await _probe_mcp_write(engine=engine, ctx=ctx, registry=registry)

    provider_pass = all(v.get("pass") for v in report["providers"].values())
    report["pass"] = bool(provider_pass and report["mcp_unified_gate"].get("pass"))
    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Live multi-provider tool + MCP write gate smoke")
    parser.add_argument("--json", dest="json_path", default=str(OUT_DEFAULT))
    args = parser.parse_args()

    print("PROBE multi_provider_tool_live", datetime.now(timezone.utc).isoformat())
    report = asyncio.run(_run_smoke(json_path=Path(args.json_path)))
    print("WROTE", args.json_path)
    print("PASS", report.get("pass"))
    for provider, payload in (report.get("providers") or {}).items():
        print(
            f"  {provider}: read={payload.get('read', {}).get('pass')} "
            f"write={payload.get('write', {}).get('pass')}"
        )
    print(f"  mcp_gate={report.get('mcp_unified_gate', {}).get('pass')}")
    if not report.get("pass"):
        print("FAIL at", report.get("failed_at") or "check/report")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
