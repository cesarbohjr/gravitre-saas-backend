"""Legal vertical pack — Clio demo connector, agents, intake workflow (STA-114)."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.services.vertical_workflow_helper import ensure_active_workflow_version
from app.workflows.audit import write_audit_event
from app.workflows.constants import SCHEMA_VERSION

logger = logging.getLogger(__name__)

LEGAL_WORKFLOW_SEED_LABEL = "workflow:legal-intake"
INTAKE_WORKFLOW_NAME = "Intake → conflict check → task assignment"
CLIO_DEMO_CONNECTOR_NAME = "Clio Demo (sandbox)"

CONFLICT_REVIEW_TASK = (
    "Review Clio contact and matter search results for this prospective client. Identify "
    "potential conflicts of interest, note adverse parties, and recommend next steps."
)

AUDIT_LEGAL_INSTALLED = "vertical.legal.installed"


def _org_namespace(org_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(org_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")


def _seed_id(org_id: str, label: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), f"gravitre-seed:{label}"))


def intake_workflow_id(org_id: str) -> str:
    return _seed_id(org_id, LEGAL_WORKFLOW_SEED_LABEL)


def intake_coordinator_agent_id(org_id: str) -> str:
    return _seed_id(org_id, "agent:intake-coordinator")


def conflict_review_agent_id(org_id: str) -> str:
    return _seed_id(org_id, "agent:conflict-review")


def clio_demo_connector_id(org_id: str) -> str:
    return _seed_id(org_id, "connector:clio-demo")


def _find_active_connector_id(
    client: Any,
    org_id: str,
    connector_type: str,
    *,
    environment_name: str = "production",
) -> str | None:
    result = (
        client.table("connectors")
        .select("id")
        .eq("org_id", org_id)
        .eq("type", connector_type)
        .eq("status", "active")
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not result.data:
        result = (
            client.table("connectors")
            .select("id")
            .eq("org_id", org_id)
            .eq("type", connector_type)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
    if not result.data:
        return None
    return str(result.data[0]["id"])


def build_intake_workflow_definition(
    *,
    org_id: str,
    clio_connector_id: str | None,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    if clio_connector_id:
        steps.extend(
            [
                {
                    "id": "contact_search",
                    "name": "Search Clio contacts",
                    "type": "invoke_tool",
                    "config": {
                        "action": "clio.contacts.search",
                        "connector_id": clio_connector_id,
                        "param_sources": {
                            "query": "$prospect_name",
                            "count": 10,
                        },
                    },
                },
                {
                    "id": "matter_search",
                    "name": "Search related matters",
                    "type": "invoke_tool",
                    "config": {
                        "action": "clio.matters.search",
                        "connector_id": clio_connector_id,
                        "param_sources": {
                            "query": "$prospect_name",
                            "client_id": "$client_id",
                            "count": 10,
                        },
                    },
                },
            ]
        )

    steps.append(
        {
            "id": "conflict_review",
            "name": "Conflict review",
            "type": "agent",
            "metadata": {
                "agent_id": conflict_review_agent_id(org_id),
                "task": CONFLICT_REVIEW_TASK,
                "briefing_from_steps": True,
            },
        }
    )

    if clio_connector_id:
        steps.extend(
            [
                {
                    "id": "conflict_checklist",
                    "name": "Generate conflict checklist",
                    "type": "invoke_tool",
                    "config": {
                        "action": "clio.conflict.checklist",
                        "connector_id": clio_connector_id,
                        "param_sources": {
                            "prospect_name": "$prospect_name",
                            "matter_type": "$matter_type",
                        },
                    },
                },
                {
                    "id": "intake_tasks",
                    "name": "Assign intake tasks",
                    "type": "invoke_tool",
                    "config": {
                        "action": "clio.intake.tasks",
                        "connector_id": clio_connector_id,
                        "param_sources": {
                            "matter_name": "$matter_name",
                        },
                    },
                },
            ]
        )
    else:
        steps.append({"id": "await_clio", "name": "Awaiting Clio connector", "type": "noop"})

    return {"schema_version": SCHEMA_VERSION, "steps": steps}


def enrich_intake_parameters(base: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    cfg = (workflow.get("config") or {}).get("legal") or {}
    out.setdefault("prospect_name", cfg.get("demo_prospect_name") or "Acme Holdings LLC")
    out.setdefault("matter_type", cfg.get("demo_matter_type") or "Corporate intake")
    out.setdefault("matter_name", base.get("matter_name") or cfg.get("demo_matter_name") or "Acme Holdings — intake")
    out.setdefault("client_id", base.get("client_id") or cfg.get("demo_client_id") or "1001")
    return out


def ensure_clio_demo_connector(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
    actor_id: str | None = None,
) -> str:
    connector_id = clio_demo_connector_id(org_id)
    row = {
        "id": connector_id,
        "org_id": org_id,
        "name": CLIO_DEMO_CONNECTOR_NAME,
        "vendor": "clio",
        "type": "clio",
        "description": "Demo Clio connector with sample contacts and matters until OAuth is connected.",
        "status": "active",
        "environment": environment_name,
        "config": {
            "sandbox": True,
            "demo": True,
        },
        "docs_url": "https://docs.developers.clio.com/",
    }
    client.table("connectors").upsert(row, on_conflict="id").execute()
    logger.info("clio_demo_connector_ensured org_id=%s connector_id=%s", org_id, connector_id)
    return connector_id


def ensure_legal_agents(client: Any, org_id: str, *, actor_id: str | None = None) -> dict[str, str]:
    intake_id = intake_coordinator_agent_id(org_id)
    conflict_id = conflict_review_agent_id(org_id)
    agents = [
        {
            "id": intake_id,
            "org_id": org_id,
            "name": "Intake Coordinator Agent",
            "purpose": "Routes new client inquiries, collects intake details, and launches conflict screening.",
            "role": "Intake Operations",
            "department": "Legal",
            "model": "claude-sonnet-4-6",
            "capabilities": ["intake", "clio-read", "task-assignment"],
            "systems": ["clio"],
            "guardrails": ["human-approval-before-engagement", "conflict-escalation-required"],
            "config": {"demo": True, "vertical": "legal", "type": "intake_coordinator"},
            "status": "active",
        },
        {
            "id": conflict_id,
            "org_id": org_id,
            "name": "Conflict Review Agent",
            "purpose": "Reviews Clio contact and matter history to flag potential conflicts before matter opening.",
            "role": "Conflicts Review",
            "department": "Legal",
            "model": "gpt-4.1",
            "capabilities": ["conflict-check", "clio-read", "ethics-review"],
            "systems": ["clio"],
            "guardrails": ["partner-escalation-on-flag", "no-legal-advice"],
            "config": {"demo": True, "vertical": "legal", "type": "conflict_review"},
            "status": "active",
        },
    ]
    client.table("agents").upsert(agents, on_conflict="id").execute()
    for agent in agents:
        upsert_agent_tool_permission(
            client,
            org_id,
            str(agent["id"]),
            connector_id=None,
            connector_type="clio",
            scopes=default_demo_scopes_for_system("clio"),
            granted_by=actor_id,
        )
    return {"intakeCoordinatorAgentId": intake_id, "conflictReviewAgentId": conflict_id}


def ensure_intake_workflow(
    client: Any,
    org_id: str,
    *,
    clio_connector_id: str | None,
    environment_name: str = "production",
    actor_id: str | None = None,
) -> str:
    workflow_id = intake_workflow_id(org_id)
    definition = build_intake_workflow_definition(org_id=org_id, clio_connector_id=clio_connector_id)
    workflow_config = {
        "demo": True,
        "legal": {
            "demo_prospect_name": "Acme Holdings LLC",
            "demo_matter_type": "Corporate intake",
            "demo_matter_name": "Acme Holdings — intake",
            "demo_client_id": "1001",
        },
    }

    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": INTAKE_WORKFLOW_NAME,
            "description": "Clio contact/matter lookup, conflict review, checklist, and intake task template.",
            "status": "active",
            "schema_version": SCHEMA_VERSION,
            "definition": definition,
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()

    client.table("workflows").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": INTAKE_WORKFLOW_NAME,
            "description": "New client intake through conflict screening and task assignment.",
            "status": "active",
            "environment": environment_name,
            "nodes": [
                {"id": "trigger", "type": "trigger", "name": "Intake received"},
                {"id": "clio", "type": "tool", "name": "Clio lookup"},
                {"id": "conflict", "type": "agent", "name": "Conflict review"},
                {"id": "tasks", "type": "tool", "name": "Task assignment"},
            ],
            "edges": [
                {"from": "trigger", "to": "clio"},
                {"from": "clio", "to": "conflict"},
                {"from": "conflict", "to": "tasks"},
            ],
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()
    ensure_active_workflow_version(
        client,
        org_id,
        workflow_id,
        definition,
        environment_name=environment_name,
        actor_id=actor_id,
    )
    return workflow_id


def get_legal_vertical_status(client: Any, org_id: str) -> dict[str, Any]:
    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = (org_row.data or [{}])[0].get("settings") or {}
    legal = settings.get("legal") if isinstance(settings.get("legal"), dict) else {}
    clio_id = legal.get("clioConnectorId") or _find_active_connector_id(client, org_id, "clio")
    return {
        "installed": bool(legal.get("installed")),
        "installedAt": legal.get("installedAt"),
        "clioConnectorId": clio_id,
        "intakeWorkflowId": legal.get("intakeWorkflowId") or intake_workflow_id(org_id),
        "intakeCoordinatorAgentId": legal.get("intakeCoordinatorAgentId") or intake_coordinator_agent_id(org_id),
        "conflictReviewAgentId": legal.get("conflictReviewAgentId") or conflict_review_agent_id(org_id),
        "clioOAuthReady": True,
    }


def install_legal_vertical_pack(
    client: Any,
    org_id: str,
    *,
    actor_id: str,
    environment_name: str = "production",
) -> dict[str, Any]:
    from datetime import datetime, timezone

    clio_connector_id = ensure_clio_demo_connector(
        client, org_id, environment_name=environment_name, actor_id=actor_id
    )
    agents = ensure_legal_agents(client, org_id, actor_id=actor_id)
    workflow_id = ensure_intake_workflow(
        client,
        org_id,
        clio_connector_id=clio_connector_id,
        environment_name=environment_name,
        actor_id=actor_id,
    )

    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = dict((org_row.data or [{}])[0].get("settings") or {})
    now = datetime.now(timezone.utc).isoformat()
    settings["legal"] = {
        "installed": True,
        "installedAt": now,
        "installedBy": actor_id,
        "clioConnectorId": clio_connector_id,
        "intakeWorkflowId": workflow_id,
        "intakeCoordinatorAgentId": agents["intakeCoordinatorAgentId"],
        "conflictReviewAgentId": agents["conflictReviewAgentId"],
    }
    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_LEGAL_INSTALLED,
        resource_type="organization",
        resource_id=org_id,
        metadata={
            "clioConnectorId": clio_connector_id,
            "intakeWorkflowId": workflow_id,
        },
    )
    logger.info(
        "legal_vertical_installed org_id=%s workflow_id=%s clio=%s",
        org_id,
        workflow_id,
        clio_connector_id,
    )
    return {
        "installed": True,
        "installedAt": now,
        "clioConnectorId": clio_connector_id,
        "intakeWorkflowId": workflow_id,
        "intakeCoordinatorAgentId": agents["intakeCoordinatorAgentId"],
        "conflictReviewAgentId": agents["conflictReviewAgentId"],
        "clioOAuthReady": True,
    }
