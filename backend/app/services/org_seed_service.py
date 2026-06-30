"""Idempotent demo seed for newly provisioned organizations."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client

from app.core.logging import get_logger
from app.services.agent_tool_permissions import (
    default_demo_scopes_for_system,
    upsert_agent_tool_permission,
)

logger = get_logger(__name__)

WELCOME_MESSAGE = (
    "Welcome to Gravitre. We've set up a sample AI team to show you what's possible. "
    "These are demo agents — connect your real tools to activate them."
)


def _seed_uuid(org_id: str, label: str) -> str:
    """Derive a stable UUID for seed rows scoped to an org."""
    return str(uuid.uuid5(uuid.UUID(org_id), f"gravitre-seed:{label}"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_org_settings(client: Client, org_id: str) -> dict[str, Any]:
    response = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    rows = response.data or []
    if not rows:
        raise ValueError(f"Organization not found: {org_id}")
    settings = rows[0].get("settings") or {}
    return settings if isinstance(settings, dict) else {}


def _save_org_settings(client: Client, org_id: str, settings: dict[str, Any]) -> None:
    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()


def _count_rows(client: Client, table: str, org_id: str) -> int:
    response = client.table(table).select("id", count="exact").eq("org_id", org_id).execute()
    return int(response.count or 0)


def build_seed_payload(org_id: str) -> dict[str, list[dict[str, Any]]]:
    """Build deterministic seed rows for a new organization."""
    now = _now()
    sales_agent_id = _seed_uuid(org_id, "agent:sales")
    marketing_agent_id = _seed_uuid(org_id, "agent:marketing")
    workflow_id = _seed_uuid(org_id, "workflow:lead-to-sequence")

    agents = [
        {
            "id": sales_agent_id,
            "org_id": org_id,
            "name": "Sales Agent",
            "purpose": "Qualifies inbound leads and routes high-intent opportunities to the right owner.",
            "role": "Sales Operations",
            "department": "Revenue",
            "model": "gpt-4.1",
            "personality": {"color": "blue", "gradient": "from-blue-500 to-indigo-500"},
            "stats": {"tasksToday": 12, "successRate": 94, "workflowsUsing": 2},
            "capabilities": ["lead-qualification", "crm-sync"],
            "systems": ["hubspot"],
            "guardrails": ["approval-for-enterprise-deals"],
            "config": {"demo": True, "type": "sales"},
            "status": "active",
            "last_action": "Qualified Acme Corp lead — score 87/100",
            "last_action_time": (now - timedelta(minutes=8)).isoformat(),
        },
        {
            "id": marketing_agent_id,
            "org_id": org_id,
            "name": "Marketing Agent",
            "purpose": "Enrolls qualified leads into nurture sequences and drafts campaign copy.",
            "role": "Marketing Operations",
            "department": "Marketing",
            "model": "claude-sonnet-4-6",
            "personality": {"color": "violet", "gradient": "from-violet-500 to-fuchsia-500"},
            "stats": {"tasksToday": 9, "successRate": 96, "workflowsUsing": 1},
            "capabilities": ["sequence-enrollment", "copy-drafting"],
            "systems": ["hubspot", "slack"],
            "guardrails": ["brand-voice-check"],
            "config": {"demo": True, "type": "marketing"},
            "status": "active",
            "last_action": "Enrolled 3 leads in 'Product Launch' sequence",
            "last_action_time": (now - timedelta(minutes=4)).isoformat(),
        },
    ]

    workflows = [
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": "New Lead → Sales qualifies → Marketing enrolls",
            "description": "Sample workflow: inbound lead is scored by Sales Agent, then handed to Marketing Agent for nurture.",
            "status": "active",
            "environment": "production",
            "nodes": [
                {"id": "trigger", "type": "trigger", "name": "New Lead"},
                {"id": "sales", "type": "agent", "name": "Sales Agent", "agent_id": sales_agent_id},
                {"id": "marketing", "type": "agent", "name": "Marketing Agent", "agent_id": marketing_agent_id},
            ],
            "edges": [
                {"from": "trigger", "to": "sales"},
                {"from": "sales", "to": "marketing"},
            ],
            "config": {"demo": True, "version": 1},
        },
    ]

    runs = [
        {
            "id": _seed_uuid(org_id, "run:1"),
            "org_id": org_id,
            "workflow_id": workflow_id,
            "workflow_name": "New Lead → Sales qualifies → Marketing enrolls",
            "status": "completed",
            "trigger": "webhook",
            "approval_status": "not_required",
            "started_at": (now - timedelta(minutes=22)).isoformat(),
            "completed_at": (now - timedelta(minutes=19)).isoformat(),
            "duration_ms": 180000,
            "metadata": {
                "demo": True,
                "output_preview": "Lead qualified: Acme Corp — enrolled in nurture sequence.",
                "recordsProcessed": 1,
            },
        },
        {
            "id": _seed_uuid(org_id, "run:2"),
            "org_id": org_id,
            "workflow_id": workflow_id,
            "workflow_name": "New Lead → Sales qualifies → Marketing enrolls",
            "status": "completed",
            "trigger": "schedule",
            "approval_status": "not_required",
            "started_at": (now - timedelta(hours=2)).isoformat(),
            "completed_at": (now - timedelta(hours=2) + timedelta(minutes=3)).isoformat(),
            "duration_ms": 195000,
            "metadata": {
                "demo": True,
                "output_preview": "Lead qualified: Northwind LLC — score 72, sequence started.",
                "recordsProcessed": 1,
            },
        },
        {
            "id": _seed_uuid(org_id, "run:3"),
            "org_id": org_id,
            "workflow_id": workflow_id,
            "workflow_name": "New Lead → Sales qualifies → Marketing enrolls",
            "status": "completed",
            "trigger": "manual",
            "approval_status": "not_required",
            "started_at": (now - timedelta(hours=5)).isoformat(),
            "completed_at": (now - timedelta(hours=5) + timedelta(minutes=2)).isoformat(),
            "duration_ms": 120000,
            "metadata": {
                "demo": True,
                "output_preview": "Lead disqualified: invalid contact — archived with reason.",
                "recordsProcessed": 1,
            },
        },
    ]

    connected_systems = [
        {
            "id": _seed_uuid(org_id, "system:hubspot"),
            "org_id": org_id,
            "system_key": "hubspot",
            "name": "HubSpot CRM (Demo)",
            "type": "crm",
            "status": "connected",
            "config": {"demo": True, "vendor": "hubspot", "requires_credentials": True},
        },
    ]

    workflow_defs = [
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": "New Lead → Sales qualifies → Marketing enrolls",
            "description": "Inbound HubSpot contact triggers qualification, then marketing nurture.",
            "status": "active",
            "schema_version": "v1",
            "definition": {
                "schema_version": "v1",
                "steps": [
                    {
                        "id": "sales_to_marketing",
                        "name": "Sales qualifies → Marketing enrolls",
                        "type": "agent",
                        "metadata": {
                            "role": "Sales",
                            "agent_id": sales_agent_id,
                            "next_agent_id": marketing_agent_id,
                            "task": "Qualify inbound lead and score fit for nurture",
                            "receiver_task": "Enroll qualified lead in nurture sequence",
                        },
                    },
                ],
            },
        },
    ]

    return {
        "agents": agents,
        "workflows": workflows,
        "workflow_defs": workflow_defs,
        "demo_hubspot_workflow_id": workflow_id,
        "runs": runs,
        "connected_systems": connected_systems,
    }


def _seed_demo_agent_tool_permissions(
    client: Client, org_id: str, agents: list[dict[str, Any]]
) -> None:
    """Grant demo agents connector-type scopes for their declared systems (STA-11)."""
    for agent in agents:
        agent_id = str(agent["id"])
        for system in agent.get("systems") or []:
            if not isinstance(system, str) or not system.strip():
                continue
            upsert_agent_tool_permission(
                client,
                org_id,
                agent_id,
                connector_id=None,
                connector_type=system.strip(),
                scopes=default_demo_scopes_for_system(system.strip()),
                granted_by=None,
            )


def seed_org_if_needed(client: Client, org_id: str) -> dict[str, Any]:
    """Seed demo agents, workflows, and runs for an org once.

    Idempotent: safe to call on every first login. Marks
    organizations.settings.onboarding.seeded when complete.
    """
    settings = _load_org_settings(client, org_id)
    onboarding = settings.get("onboarding")
    if not isinstance(onboarding, dict):
        onboarding = {}

    if onboarding.get("seeded") is True:
        return {
            "org_id": org_id,
            "seeded": True,
            "agents_created": _count_rows(client, "agents", org_id),
            "workflows_created": _count_rows(client, "workflows", org_id),
            "runs_created": _count_rows(client, "runs", org_id),
            "welcome_message": WELCOME_MESSAGE,
        }

    payload = build_seed_payload(org_id)

    client.table("agents").upsert(payload["agents"], on_conflict="id").execute()
    _seed_demo_agent_tool_permissions(client, org_id, payload["agents"])
    client.table("workflows").upsert(payload["workflows"], on_conflict="id").execute()
    if payload.get("workflow_defs"):
        client.table("workflow_defs").upsert(payload["workflow_defs"], on_conflict="id").execute()
    client.table("runs").upsert(payload["runs"], on_conflict="id").execute()
    client.table("connected_systems").upsert(payload["connected_systems"], on_conflict="id").execute()

    try:
        from app.services.council_workflow_service import ensure_uncertain_lead_council_workflow

        council_wf_id = ensure_uncertain_lead_council_workflow(client, org_id)
        onboarding["demo_council_workflow_id"] = council_wf_id
    except Exception:  # noqa: BLE001
        pass

    onboarding["seeded"] = True
    if payload.get("demo_hubspot_workflow_id"):
        onboarding["demo_hubspot_workflow_id"] = payload["demo_hubspot_workflow_id"]
    onboarding["seeded_at"] = _now().isoformat()
    onboarding.setdefault("checklist_dismissed", False)
    settings["onboarding"] = onboarding
    _save_org_settings(client, org_id, settings)

    try:
        from app.config import get_settings
        from app.services.platform_knowledge_seed import seed_platform_knowledge_for_org

        seed_platform_knowledge_for_org(client, org_id, get_settings(), environment_name="production")
    except Exception as exc:  # noqa: BLE001
        logger.debug("platform_knowledge_seed_skipped org_id=%s error=%s", org_id, str(exc))

    return {
        "org_id": org_id,
        "seeded": True,
        "agents_created": len(payload["agents"]),
        "workflows_created": len(payload["workflows"]),
        "runs_created": len(payload["runs"]),
        "welcome_message": WELCOME_MESSAGE,
    }
