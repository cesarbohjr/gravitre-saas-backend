"""Enterprise nurture workflow templates — Marketo + handoff bus (STA-66)."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import Settings
from app.services.council_workflow_service import marketing_agent_id, sales_agent_id
from app.workflows.constants import SCHEMA_VERSION

logger = logging.getLogger(__name__)

ABM_HANDOFF_SEED_LABEL = "workflow:marketo-abm-handoff"
ABM_HANDOFF_NAME = "ABM handoff — Sales → Marketo"
WEBINAR_FOLLOWUP_SEED_LABEL = "workflow:marketo-webinar-followup"
WEBINAR_FOLLOWUP_NAME = "Webinar follow-up — Segment → Marketo nurture"


def _org_namespace(org_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(org_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")


def abm_handoff_workflow_id(org_id: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), f"gravitre-seed:{ABM_HANDOFF_SEED_LABEL}"))


def webinar_followup_workflow_id(org_id: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), f"gravitre-seed:{WEBINAR_FOLLOWUP_SEED_LABEL}"))


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


def build_abm_handoff_workflow_definition(
    *,
    org_id: str,
    marketo_connector_id: str | None,
) -> dict[str, Any]:
    """Sales qualifies account → handoff bus → Marketing updates Marketo lead + list."""
    sales_id = sales_agent_id(org_id)
    marketing_id = marketing_agent_id(org_id)
    steps: list[dict[str, Any]] = [
        {
            "id": "sales_abm_qualify",
            "name": "Sales qualifies ABM target",
            "type": "agent",
            "metadata": {
                "agent_id": sales_id,
                "next_agent_id": marketing_id,
                "briefing_from_steps": True,
                "task": (
                    "Review the ABM account briefing. Score fit and intent. "
                    "Summarize why this account should enter the Marketo ABM program."
                ),
                "receiver_task": "Prepare Marketo updates for the qualified ABM account.",
            },
        },
    ]
    if marketo_connector_id:
        steps.append(
            {
                "id": "marketo_update_lead",
                "name": "Update Marketo lead for ABM",
                "type": "invoke_tool",
                "config": {
                    "action": "marketo.leads.update",
                    "connector_id": marketo_connector_id,
                    "param_sources": {
                        "action": "updateOnly",
                        "leads": "$marketo_leads",
                    },
                },
            }
        )
        steps.append(
            {
                "id": "marketo_abm_list",
                "name": "Add lead to ABM static list",
                "type": "invoke_tool",
                "config": {
                    "action": "marketo.lists.add_to_static_list",
                    "connector_id": marketo_connector_id,
                    "param_sources": {
                        "list_id": "$abm_list_id",
                        "emails": "$abm_emails",
                    },
                },
            }
        )
    steps.append(
        {
            "id": "marketing_confirm",
            "name": "Marketing confirms ABM handoff",
            "type": "agent",
            "metadata": {
                "agent_id": marketing_id,
                "briefing_from_steps": True,
                "task": "Confirm ABM handoff completed and note next nurture actions.",
            },
        }
    )
    return {"schema_version": SCHEMA_VERSION, "steps": steps}


def build_webinar_followup_workflow_definition(
    *,
    org_id: str,
    marketo_connector_id: str | None,
) -> dict[str, Any]:
    """Inbound webinar attendee event → handoff → Marketo program status + nurture list."""
    marketing_id = marketing_agent_id(org_id)
    steps: list[dict[str, Any]] = [
        {
            "id": "webinar_intake",
            "name": "Process webinar attendee context",
            "type": "agent",
            "metadata": {
                "agent_id": marketing_id,
                "briefing_from_steps": True,
                "task": (
                    "Review the Segment webinar attendee event. Summarize engagement "
                    "and recommend nurture track (hot / warm / replay)."
                ),
            },
        },
    ]
    if marketo_connector_id:
        steps.append(
            {
                "id": "marketo_program_status",
                "name": "Check Marketo webinar program status",
                "type": "invoke_tool",
                "config": {
                    "action": "marketo.programs.status",
                    "connector_id": marketo_connector_id,
                    "param_sources": {"program_id": "$webinar_program_id"},
                },
            }
        )
        steps.append(
            {
                "id": "marketo_nurture_list",
                "name": "Add attendee to nurture static list",
                "type": "invoke_tool",
                "config": {
                    "action": "marketo.lists.add_to_static_list",
                    "connector_id": marketo_connector_id,
                    "param_sources": {
                        "list_id": "$nurture_list_id",
                        "emails": "$attendee_emails",
                    },
                },
            }
        )
    steps.append(
        {
            "id": "marketing_followup",
            "name": "Marketing follow-up plan",
            "type": "agent",
            "metadata": {
                "agent_id": marketing_id,
                "briefing_from_steps": True,
                "task": "Draft follow-up actions for the webinar attendee based on program status.",
            },
        }
    )
    return {"schema_version": SCHEMA_VERSION, "steps": steps}


def _upsert_workflow(
    client: Any,
    org_id: str,
    *,
    workflow_id: str,
    name: str,
    description: str,
    definition: dict[str, Any],
    config: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    environment_name: str = "production",
) -> str:
    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": name,
            "description": description,
            "status": "active",
            "schema_version": SCHEMA_VERSION,
            "definition": definition,
            "config": config,
        },
        on_conflict="id",
    ).execute()

    client.table("workflows").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": name,
            "description": description,
            "status": "active",
            "environment": environment_name,
            "nodes": nodes,
            "edges": edges,
            "config": config,
        },
        on_conflict="id",
    ).execute()
    return workflow_id


def ensure_abm_handoff_workflow(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> str:
    workflow_id = abm_handoff_workflow_id(org_id)
    marketo_id = _find_active_connector_id(client, org_id, "marketo", environment_name=environment_name)
    definition = build_abm_handoff_workflow_definition(org_id=org_id, marketo_connector_id=marketo_id)
    config = {"demo": True, "marketo_abm_handoff": True}
    nodes = [
        {"id": "sales", "type": "agent", "name": "Sales qualify"},
        {"id": "marketo", "type": "invoke_tool", "name": "Marketo update"},
        {"id": "marketing", "type": "agent", "name": "Marketing confirm"},
    ]
    edges = [
        {"from": "sales", "to": "marketo"},
        {"from": "marketo", "to": "marketing"},
    ]
    _upsert_workflow(
        client,
        org_id,
        workflow_id=workflow_id,
        name=ABM_HANDOFF_NAME,
        description="Sales agent handoff to Marketing with Marketo ABM list enrollment.",
        definition=definition,
        config=config,
        nodes=nodes,
        edges=edges,
        environment_name=environment_name,
    )
    logger.info("marketo_abm_workflow_ensured org_id=%s workflow_id=%s", org_id, workflow_id)
    return workflow_id


def ensure_webinar_followup_workflow(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> str:
    workflow_id = webinar_followup_workflow_id(org_id)
    marketo_id = _find_active_connector_id(client, org_id, "marketo", environment_name=environment_name)
    definition = build_webinar_followup_workflow_definition(org_id=org_id, marketo_connector_id=marketo_id)
    config = {"demo": True, "marketo_webinar_followup": True, "handoff_bus": True}
    nodes = [
        {"id": "intake", "type": "agent", "name": "Webinar intake"},
        {"id": "program", "type": "invoke_tool", "name": "Program status"},
        {"id": "nurture", "type": "invoke_tool", "name": "Nurture list"},
        {"id": "followup", "type": "agent", "name": "Follow-up"},
    ]
    edges = [
        {"from": "intake", "to": "program"},
        {"from": "program", "to": "nurture"},
        {"from": "nurture", "to": "followup"},
    ]
    _upsert_workflow(
        client,
        org_id,
        workflow_id=workflow_id,
        name=WEBINAR_FOLLOWUP_NAME,
        description="Segment webinar attendee trigger with Marketo nurture via handoff bus.",
        definition=definition,
        config=config,
        nodes=nodes,
        edges=edges,
        environment_name=environment_name,
    )
    logger.info("marketo_webinar_workflow_ensured org_id=%s workflow_id=%s", org_id, workflow_id)
    return workflow_id


def ensure_marketo_workflow_templates(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> dict[str, str]:
    """Upsert both Marketo workflow templates for an org."""
    return {
        "abm_handoff": ensure_abm_handoff_workflow(client, org_id, environment_name=environment_name),
        "webinar_followup": ensure_webinar_followup_workflow(client, org_id, environment_name=environment_name),
    }


def on_marketo_org_ready(client: Any, org_id: str, settings: Settings) -> None:
    _ = settings
    try:
        ensure_marketo_workflow_templates(client, org_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("marketo_workflow_setup_failed org_id=%s error=%s", org_id, exc)
