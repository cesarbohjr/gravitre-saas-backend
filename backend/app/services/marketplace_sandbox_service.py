"""Partner marketplace sandbox org provisioning (STA-72)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import Settings
from app.connectors.partners.acme_tools_demo import ensure_acme_tools_demo_registered
from app.connectors.platform import store_connector_api_key
from app.core.errors import error_detail
from app.services.agent_tool_permissions import upsert_agent_tool_permission
from app.services.org_seed_service import _seed_uuid

RESOURCE_TYPE_MARKETPLACE_SANDBOX = "marketplace_sandbox"
AUDIT_SANDBOX_PROVISIONED = "marketplace.sandbox.provisioned"
AUDIT_SANDBOX_RESET = "marketplace.sandbox.reset"
AUDIT_SANDBOX_DEMO = "marketplace.sandbox.demo_ran"

DEMO_INVOKE_ACTION = "acme_tools.tickets.list"

SANDBOX_WELCOME = (
    "This is your isolated partner sandbox. Demo agents, mock connectors, and sample workflows "
    "are pre-loaded for connector QA. Changes here do not affect your production workspace."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "partner-sandbox"


def _load_org_name(client: Any, org_id: str) -> str:
    row = client.table("organizations").select("name").eq("id", org_id).limit(1).execute()
    if not row.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publisher organization not found")
    return str(row.data[0].get("name") or "Partner")


def get_sandbox_mapping(client: Any, publisher_org_id: str) -> dict[str, Any] | None:
    """Return sandbox mapping row for a publisher org, if any."""
    result = (
        client.table("marketplace_sandbox_orgs")
        .select("*")
        .eq("publisher_org_id", publisher_org_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def build_marketplace_sandbox_payload(org_id: str) -> dict[str, list[dict[str, Any]]]:
    """Deterministic demo data for partner connector QA."""
    now = _now()
    qa_agent_id = _seed_uuid(org_id, "agent:integration-qa")
    workflow_id = _seed_uuid(org_id, "workflow:partner-connector-test")
    acme_connector_id = _seed_uuid(org_id, "connector:acme-tools")

    agents = [
        {
            "id": qa_agent_id,
            "org_id": org_id,
            "name": "Integration QA Agent",
            "purpose": "Tests partner connector actions in the marketplace sandbox using invoke_tool.",
            "role": "Integration QA",
            "department": "Platform",
            "model": "gpt-4.1",
            "personality": {"color": "emerald", "gradient": "from-emerald-500 to-teal-500"},
            "stats": {"tasksToday": 4, "successRate": 100, "workflowsUsing": 1},
            "capabilities": ["connector-testing", "invoke-tool"],
            "systems": ["acme_tools", "hubspot"],
            "guardrails": ["sandbox-only"],
            "config": {"demo": True, "sandbox": True, "type": "integration_qa"},
            "status": "active",
            "last_action": "Listed 3 mock Acme Tools tickets (demo)",
            "last_action_time": (now - timedelta(minutes=2)).isoformat(),
        },
    ]

    workflows = [
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": "Partner connector smoke test",
            "description": "Invoke partner tool actions and verify audit trail in sandbox.",
            "status": "active",
            "environment": "staging",
            "nodes": [
                {"id": "trigger", "type": "trigger", "name": "Manual test"},
                {
                    "id": "invoke",
                    "type": "invoke_tool",
                    "name": "List Acme tickets",
                    "config": {"action": "acme_tools.tickets.list", "params": {"status": "open", "limit": 5}},
                },
            ],
            "edges": [{"from": "trigger", "to": "invoke"}],
            "config": {"demo": True, "sandbox": True},
        },
    ]

    workflow_defs = [
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": "Partner connector smoke test",
            "description": "Sandbox workflow for partner connector invoke_tool verification.",
            "status": "active",
            "schema_version": "v1",
            "definition": {
                "schema_version": "v1",
                "steps": [
                    {
                        "id": "list_tickets",
                        "name": "List Acme tickets",
                        "type": "invoke_tool",
                        "metadata": {
                            "action": "acme_tools.tickets.list",
                            "params": {"status": "open", "limit": 5},
                        },
                    },
                ],
            },
        },
    ]

    runs = [
        {
            "id": _seed_uuid(org_id, "run:sandbox-smoke"),
            "org_id": org_id,
            "workflow_id": workflow_id,
            "workflow_name": "Partner connector smoke test",
            "status": "completed",
            "trigger": "manual",
            "approval_status": "not_required",
            "started_at": (now - timedelta(minutes=10)).isoformat(),
            "completed_at": (now - timedelta(minutes=9)).isoformat(),
            "duration_ms": 42000,
            "metadata": {
                "demo": True,
                "sandbox": True,
                "output_preview": "acme_tools.tickets.list → 2 open tickets",
                "recordsProcessed": 2,
            },
        },
    ]

    connectors = [
        {
            "id": acme_connector_id,
            "org_id": org_id,
            "name": "acme-tools",
            "vendor": "acme_tools",
            "type": "acme_tools",
            "description": "Acme Tools (sandbox demo)",
            "status": "healthy",
            "environment": "staging",
            "sync_frequency": "1h",
            "config": {"auth_type": "apiKey", "demo": True, "sandbox": True},
            "docs_url": "https://example.com/acme-tools",
        },
    ]

    connected_systems = [
        {
            "id": _seed_uuid(org_id, "system:acme-tools"),
            "org_id": org_id,
            "system_key": "acme_tools",
            "name": "Acme Tools (Sandbox)",
            "type": "partner",
            "status": "connected",
            "config": {"demo": True, "vendor": "acme_tools", "sandbox": True},
        },
    ]

    return {
        "agents": agents,
        "workflows": workflows,
        "workflow_defs": workflow_defs,
        "runs": runs,
        "connectors": connectors,
        "connected_systems": connected_systems,
        "qa_agent_id": qa_agent_id,
        "acme_connector_id": acme_connector_id,
    }


def _seed_sandbox_data(client: Any, org_id: str, settings: Settings) -> dict[str, Any]:
    """Insert or refresh sandbox demo rows."""
    ensure_acme_tools_demo_registered()
    payload = build_marketplace_sandbox_payload(org_id)

    client.table("agents").upsert(payload["agents"], on_conflict="id").execute()
    client.table("workflows").upsert(payload["workflows"], on_conflict="id").execute()
    client.table("workflow_defs").upsert(payload["workflow_defs"], on_conflict="id").execute()
    client.table("runs").upsert(payload["runs"], on_conflict="id").execute()
    client.table("connected_systems").upsert(payload["connected_systems"], on_conflict="id").execute()
    client.table("connectors").upsert(payload["connectors"], on_conflict="id").execute()

    acme_id = str(payload["acme_connector_id"])
    store_connector_api_key(client, org_id, acme_id, "sandbox-demo-acme-key", settings)

    qa_agent_id = str(payload["qa_agent_id"])
    upsert_agent_tool_permission(
        client,
        org_id,
        qa_agent_id,
        connector_id=acme_id,
        connector_type="acme_tools",
        scopes=["acme_tools:tickets:read", "acme_tools:tickets:write", "acme_tools:*"],
        granted_by=None,
    )
    upsert_agent_tool_permission(
        client,
        org_id,
        qa_agent_id,
        connector_id=None,
        connector_type="hubspot",
        scopes=["hubspot:*"],
        granted_by=None,
    )

    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings_doc = (org_row.data[0].get("settings") if org_row.data else {}) or {}
    if not isinstance(settings_doc, dict):
        settings_doc = {}
    marketplace = settings_doc.get("marketplace")
    if not isinstance(marketplace, dict):
        marketplace = {}
    marketplace["sandbox"] = True
    marketplace["sandbox_seeded_at"] = _now().isoformat()
    marketplace["welcome_message"] = SANDBOX_WELCOME
    settings_doc["marketplace"] = marketplace
    settings_doc["onboarding"] = {
        "seeded": True,
        "seeded_at": _now().isoformat(),
        "checklist_dismissed": True,
        "completed_at": _now().isoformat(),
        "completed_steps": ["sandbox"],
    }
    client.table("organizations").update({"settings": settings_doc}).eq("id", org_id).execute()

    return {
        "agents_created": len(payload["agents"]),
        "workflows_created": len(payload["workflows"]),
        "connectors_created": len(payload["connectors"]),
        "welcome_message": SANDBOX_WELCOME,
    }


def _create_sandbox_org(client: Any, publisher_org_id: str, publisher_name: str) -> str:
    """Create isolated sandbox organization with billing exempt from trial gate."""
    suffix = publisher_org_id.replace("-", "")[:8]
    slug = f"{_slugify(publisher_name)}-sandbox-{suffix}"
    org_settings = {
        "marketplace": {"sandbox": True, "publisher_org_id": publisher_org_id},
        "onboarding": {"seeded": False, "checklist_dismissed": True},
        "billing": {"sandbox_exempt": True},
    }
    created = (
        client.table("organizations")
        .insert(
            {
                "name": f"Partner Sandbox · {publisher_name}",
                "slug": slug,
                "status": "active",
                "settings": org_settings,
            }
        )
        .select("id, name, slug")
        .limit(1)
        .execute()
    )
    if not created.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Sandbox org create failed")
    sandbox_org_id = str(created.data[0]["id"])

    trial_end = _now() + timedelta(days=365)
    client.table("org_billing").upsert(
        {
            "org_id": sandbox_org_id,
            "plan_code": "node",
            "billing_status": "active",
            "current_period_end": trial_end.isoformat(),
            "cancel_at_period_end": False,
        },
        on_conflict="org_id",
    ).execute()
    return sandbox_org_id


def provision_sandbox(
    client: Any,
    settings: Settings,
    *,
    publisher_org_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Provision or return existing partner sandbox org for a publisher."""
    existing = get_sandbox_mapping(client, publisher_org_id)
    if existing:
        sandbox_org_id = str(existing["sandbox_org_id"])
        org = client.table("organizations").select("id, name, slug").eq("id", sandbox_org_id).limit(1).execute()
        if not org.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Sandbox org missing")
        seed_stats = _seed_sandbox_data(client, sandbox_org_id, settings)
        return _normalize_status(existing, org.data[0], seed_stats, created=False)

    publisher_name = _load_org_name(client, publisher_org_id)
    sandbox_org_id = _create_sandbox_org(client, publisher_org_id, publisher_name)

    membership = client.table("organization_members").select("id").eq("user_id", user_id).eq("org_id", publisher_org_id).limit(1).execute()
    if not membership.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of publisher organization")

    client.table("organization_members").insert(
        {"id": str(uuid4()), "org_id": sandbox_org_id, "user_id": user_id, "role": "admin"}
    ).execute()

    mapping = (
        client.table("marketplace_sandbox_orgs")
        .insert(
            {
                "publisher_org_id": publisher_org_id,
                "sandbox_org_id": sandbox_org_id,
                "created_by": user_id,
            }
        )
        .select("*")
        .limit(1)
        .execute()
    )
    if not mapping.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Sandbox mapping create failed")

    seed_stats = _seed_sandbox_data(client, sandbox_org_id, settings)
    org = client.table("organizations").select("id, name, slug").eq("id", sandbox_org_id).limit(1).execute()
    return _normalize_status(mapping.data[0], org.data[0], seed_stats, created=True)


def reset_sandbox(client: Any, settings: Settings, *, publisher_org_id: str) -> dict[str, Any]:
    """Re-seed sandbox demo data for a publisher org."""
    mapping = get_sandbox_mapping(client, publisher_org_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("Sandbox not provisioned for this organization", "SANDBOX_NOT_FOUND"),
        )
    sandbox_org_id = str(mapping["sandbox_org_id"])
    seed_stats = _seed_sandbox_data(client, sandbox_org_id, settings)
    org = client.table("organizations").select("id, name, slug").eq("id", sandbox_org_id).limit(1).execute()
    if not org.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox org not found")
    return _normalize_status(mapping, org.data[0], seed_stats, created=False, reset=True)


def _normalize_audit_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id")),
        "action": row.get("action"),
        "resourceType": row.get("resource_type"),
        "resourceId": str(row.get("resource_id")) if row.get("resource_id") else None,
        "metadata": row.get("metadata") or {},
        "createdAt": row.get("created_at"),
    }


def _fetch_recent_audit_trail(client: Any, org_id: str, *, limit: int = 12) -> list[dict[str, Any]]:
    """Return recent tool-invoke and marketplace demo audit rows for sandbox org."""
    actions = [
        "tool.invoke.requested",
        "tool.invoke.completed",
        "tool.invoke.failed",
        AUDIT_SANDBOX_DEMO,
    ]
    result = (
        client.table("audit_events")
        .select("id, action, resource_type, resource_id, metadata, created_at")
        .eq("org_id", org_id)
        .in_("action", actions)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_normalize_audit_row(row) for row in (result.data or [])]


def run_sandbox_demo(
    client: Any,
    settings: Settings,
    *,
    publisher_org_id: str,
    actor_id: str,
) -> dict[str, Any]:
    """STA-73: Invoke Acme Tools in sandbox as Integration QA Agent and return audit trail."""
    from app.connectors.partners.acme_tools_demo import ensure_acme_tools_demo_registered
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext
    from app.workflows.audit import write_audit_event

    mapping = get_sandbox_mapping(client, publisher_org_id)
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_detail("Sandbox not provisioned for this organization", "SANDBOX_NOT_FOUND"),
        )

    sandbox_org_id = str(mapping["sandbox_org_id"])
    qa_agent_id = _seed_uuid(sandbox_org_id, "agent:integration-qa")
    acme_connector_id = _seed_uuid(sandbox_org_id, "connector:acme-tools")

    ensure_acme_tools_demo_registered()

    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=sandbox_org_id,
        actor_id=actor_id,
        agent_id=qa_agent_id,
        connector_id=acme_connector_id,
        environment_name="staging",
    )
    invoke_result = invoke_tool(
        ctx,
        DEMO_INVOKE_ACTION,
        {"connector_id": acme_connector_id, "status": "open", "limit": 3},
    )

    ticket_count = len(invoke_result.data.get("tickets") or []) if invoke_result.success else 0
    write_audit_event(
        client,
        org_id=sandbox_org_id,
        actor_id=actor_id,
        action=AUDIT_SANDBOX_DEMO,
        resource_type=RESOURCE_TYPE_MARKETPLACE_SANDBOX,
        resource_id=acme_connector_id,
        metadata={
            "action": DEMO_INVOKE_ACTION,
            "agentId": qa_agent_id,
            "connectorId": acme_connector_id,
            "success": invoke_result.success,
            "ticketCount": ticket_count,
        },
    )

    return {
        "sandboxOrgId": sandbox_org_id,
        "agentId": qa_agent_id,
        "agentName": "Integration QA Agent",
        "connectorId": acme_connector_id,
        "connectorName": "Acme Tools (sandbox demo)",
        "action": DEMO_INVOKE_ACTION,
        "success": invoke_result.success,
        "tickets": invoke_result.data.get("tickets") or [] if invoke_result.success else [],
        "errorCode": invoke_result.error_code,
        "errorMessage": invoke_result.error_message,
        "auditTrail": _fetch_recent_audit_trail(client, sandbox_org_id),
    }


def get_sandbox_status(client: Any, publisher_org_id: str) -> dict[str, Any]:
    """Return sandbox provisioning status for publisher org."""
    mapping = get_sandbox_mapping(client, publisher_org_id)
    if not mapping:
        return {"provisioned": False, "publisherOrgId": publisher_org_id}
    sandbox_org_id = str(mapping["sandbox_org_id"])
    org = client.table("organizations").select("id, name, slug, settings").eq("id", sandbox_org_id).limit(1).execute()
    if not org.data:
        return {"provisioned": False, "publisherOrgId": publisher_org_id}
    row = org.data[0]
    settings_doc = row.get("settings") or {}
    marketplace = settings_doc.get("marketplace") if isinstance(settings_doc, dict) else {}
    return {
        "provisioned": True,
        "publisherOrgId": publisher_org_id,
        "sandboxOrgId": sandbox_org_id,
        "sandboxOrgName": row.get("name"),
        "sandboxOrgSlug": row.get("slug"),
        "seededAt": marketplace.get("sandbox_seeded_at") if isinstance(marketplace, dict) else None,
        "welcomeMessage": SANDBOX_WELCOME,
        "createdAt": mapping.get("created_at"),
    }


def _normalize_status(
    mapping: dict[str, Any],
    org_row: dict[str, Any],
    seed_stats: dict[str, Any],
    *,
    created: bool,
    reset: bool = False,
) -> dict[str, Any]:
    return {
        "provisioned": True,
        "created": created,
        "reset": reset,
        "publisherOrgId": str(mapping["publisher_org_id"]),
        "sandboxOrgId": str(org_row["id"]),
        "sandboxOrgName": org_row.get("name"),
        "sandboxOrgSlug": org_row.get("slug"),
        "welcomeMessage": seed_stats.get("welcome_message", SANDBOX_WELCOME),
        "agentsCreated": seed_stats.get("agents_created", 0),
        "workflowsCreated": seed_stats.get("workflows_created", 0),
        "connectorsCreated": seed_stats.get("connectors_created", 0),
    }
