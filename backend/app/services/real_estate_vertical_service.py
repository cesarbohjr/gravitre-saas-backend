"""Real estate vertical pack — listing workflow with HubSpot/Salesforce (STA-115)."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.services.vertical_workflow_helper import ensure_active_workflow_version
from app.workflows.audit import write_audit_event
from app.workflows.constants import SCHEMA_VERSION
from app.core.safe_dict import safe_normalize_stored_dict

logger = logging.getLogger(__name__)

REAL_ESTATE_WORKFLOW_SEED_LABEL = "workflow:real-estate-listing"
LISTING_WORKFLOW_NAME = "New listing → MLS note → buyer agent handoff"
LISTING_COORDINATOR_TASK = (
    "Review the listing details and HubSpot buyer context. Draft an MLS-ready property summary "
    "and highlight items the buyer agent needs before showings."
)
BUYER_AGENT_TASK = (
    "Using the MLS note and buyer search results, prepare a concise handoff brief for the buyer agent "
    "including tour plan, financing notes, and recommended next steps."
)

AUDIT_REAL_ESTATE_INSTALLED = "vertical.real_estate.installed"


def _org_namespace(org_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(org_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")


def _seed_id(org_id: str, label: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), f"gravitre-seed:{label}"))


def listing_workflow_id(org_id: str) -> str:
    return _seed_id(org_id, REAL_ESTATE_WORKFLOW_SEED_LABEL)


def listing_coordinator_agent_id(org_id: str) -> str:
    return _seed_id(org_id, "agent:listing-coordinator")


def buyer_agent_id(org_id: str) -> str:
    return _seed_id(org_id, "agent:buyer-agent")


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


def build_listing_workflow_definition(
    *,
    org_id: str,
    hubspot_connector_id: str | None,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    if hubspot_connector_id:
        steps.append(
            {
                "id": "buyer_search",
                "name": "Search HubSpot buyers",
                "type": "invoke_tool",
                "config": {
                    "action": "hubspot.contacts.search",
                    "connector_id": hubspot_connector_id,
                    "param_sources": {
                        "filter_groups": [
                            {
                                "filters": [
                                    {
                                        "propertyName": "email",
                                        "operator": "CONTAINS_TOKEN",
                                        "value": "$buyer_email",
                                    }
                                ]
                            }
                        ],
                        "properties": ["email", "firstname", "lastname", "phone"],
                        "limit": 5,
                    },
                },
            }
        )

    steps.append(
        {
            "id": "mls_note",
            "name": "Draft MLS note",
            "type": "invoke_tool",
            "config": {
                "action": "real_estate.mls.note",
                "param_sources": {
                    "property_address": "$property_address",
                    "list_price": "$list_price",
                },
            },
        }
    )

    steps.append(
        {
            "id": "listing_review",
            "name": "Listing coordinator review",
            "type": "agent",
            "metadata": {
                "agent_id": listing_coordinator_agent_id(org_id),
                "task": LISTING_COORDINATOR_TASK,
                "briefing_from_steps": True,
            },
        }
    )

    steps.append(
        {
            "id": "buyer_handoff",
            "name": "Buyer agent handoff",
            "type": "agent",
            "metadata": {
                "agent_id": buyer_agent_id(org_id),
                "task": BUYER_AGENT_TASK,
                "briefing_from_steps": True,
            },
        }
    )

    steps.append(
        {
            "id": "handoff_brief",
            "name": "Generate handoff brief",
            "type": "invoke_tool",
            "config": {
                "action": "real_estate.handoff.brief",
                "param_sources": {
                    "buyer_name": "$buyer_name",
                    "property_address": "$property_address",
                },
            },
        }
    )

    return {"schema_version": SCHEMA_VERSION, "steps": steps}


def enrich_listing_parameters(base: dict[str, Any], workflow: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    cfg = (workflow.get("config") or {}).get("real_estate") or {}
    out.setdefault("property_address", cfg.get("demo_property_address") or "742 Evergreen Terrace")
    out.setdefault("list_price", cfg.get("demo_list_price") or "450000")
    out.setdefault("buyer_name", cfg.get("demo_buyer_name") or "Jamie Buyer")
    out.setdefault("buyer_email", cfg.get("demo_buyer_email") or "buyer@example.com")
    return out


def ensure_real_estate_agents(client: Any, org_id: str, *, actor_id: str | None = None) -> dict[str, str]:
    listing_id = listing_coordinator_agent_id(org_id)
    buyer_id = buyer_agent_id(org_id)
    agents = [
        {
            "id": listing_id,
            "org_id": org_id,
            "name": "Listing Coordinator Agent",
            "purpose": "Prepares MLS notes and coordinates listing launch tasks.",
            "role": "Listing Operations",
            "department": "Real Estate",
            "model": "claude-sonnet-4-6",
            "capabilities": ["listing-intake", "mls-notes", "hubspot-read"],
            "systems": ["hubspot", "real_estate"],
            "guardrails": ["human-approval-before-mls-publish"],
            "config": {"demo": True, "vertical": "real_estate", "type": "listing_coordinator"},
            "status": "active",
        },
        {
            "id": buyer_id,
            "org_id": org_id,
            "name": "Buyer Agent Handoff Agent",
            "purpose": "Packages buyer context and listing details for agent handoff.",
            "role": "Buyer Services",
            "department": "Real Estate",
            "model": "gpt-4.1",
            "capabilities": ["buyer-handoff", "hubspot-read", "tour-planning"],
            "systems": ["hubspot", "real_estate"],
            "guardrails": ["no-financial-advice"],
            "config": {"demo": True, "vertical": "real_estate", "type": "buyer_agent"},
            "status": "active",
        },
    ]
    client.table("agents").upsert(agents, on_conflict="id").execute()
    for agent in agents:
        for system in ("hubspot", "real_estate"):
            upsert_agent_tool_permission(
                client,
                org_id,
                str(agent["id"]),
                connector_id=None,
                connector_type=system,
                scopes=default_demo_scopes_for_system(system),
                granted_by=actor_id,
            )
    return {"listingCoordinatorAgentId": listing_id, "buyerAgentId": buyer_id}


def ensure_listing_workflow(
    client: Any,
    org_id: str,
    *,
    hubspot_connector_id: str | None,
    environment_name: str = "production",
    actor_id: str | None = None,
) -> str:
    workflow_id = listing_workflow_id(org_id)
    definition = build_listing_workflow_definition(org_id=org_id, hubspot_connector_id=hubspot_connector_id)
    workflow_config = {
        "demo": True,
        "real_estate": {
            "demo_property_address": "742 Evergreen Terrace",
            "demo_list_price": "450000",
            "demo_buyer_name": "Jamie Buyer",
            "demo_buyer_email": "buyer@example.com",
        },
    }

    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": LISTING_WORKFLOW_NAME,
            "description": "New listing intake, MLS note, coordinator review, buyer agent handoff.",
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
            "name": LISTING_WORKFLOW_NAME,
            "description": "Listing launch through buyer agent handoff.",
            "status": "active",
            "environment": environment_name,
            "nodes": [
                {"id": "trigger", "type": "trigger", "name": "New listing"},
                {"id": "crm", "type": "tool", "name": "Buyer lookup"},
                {"id": "mls", "type": "tool", "name": "MLS note"},
                {"id": "handoff", "type": "agent", "name": "Buyer handoff"},
            ],
            "edges": [
                {"from": "trigger", "to": "crm"},
                {"from": "crm", "to": "mls"},
                {"from": "mls", "to": "handoff"},
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


def get_real_estate_vertical_status(client: Any, org_id: str) -> dict[str, Any]:
    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = (org_row.data or [{}])[0].get("settings") or {}
    re_cfg = settings.get("real_estate") if isinstance(settings.get("real_estate"), dict) else {}
    hubspot_id = re_cfg.get("hubspotConnectorId") or _find_active_connector_id(client, org_id, "hubspot")
    return {
        "installed": bool(re_cfg.get("installed")),
        "installedAt": re_cfg.get("installedAt"),
        "hubspotConnectorId": hubspot_id,
        "listingWorkflowId": re_cfg.get("listingWorkflowId") or listing_workflow_id(org_id),
        "listingCoordinatorAgentId": re_cfg.get("listingCoordinatorAgentId") or listing_coordinator_agent_id(org_id),
        "buyerAgentId": re_cfg.get("buyerAgentId") or buyer_agent_id(org_id),
    }


def install_real_estate_vertical_pack(
    client: Any,
    org_id: str,
    *,
    actor_id: str,
    environment_name: str = "production",
) -> dict[str, Any]:
    from datetime import datetime, timezone

    hubspot_connector_id = _find_active_connector_id(client, org_id, "hubspot", environment_name=environment_name)
    agents = ensure_real_estate_agents(client, org_id, actor_id=actor_id)
    workflow_id = ensure_listing_workflow(
        client,
        org_id,
        hubspot_connector_id=hubspot_connector_id,
        environment_name=environment_name,
        actor_id=actor_id,
    )

    org_row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = safe_normalize_stored_dict((org_row.data or [{}])[0], key='settings')
    now = datetime.now(timezone.utc).isoformat()
    settings["real_estate"] = {
        "installed": True,
        "installedAt": now,
        "installedBy": actor_id,
        "hubspotConnectorId": hubspot_connector_id,
        "listingWorkflowId": workflow_id,
        "listingCoordinatorAgentId": agents["listingCoordinatorAgentId"],
        "buyerAgentId": agents["buyerAgentId"],
    }
    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_REAL_ESTATE_INSTALLED,
        resource_type="organization",
        resource_id=org_id,
        metadata={"listingWorkflowId": workflow_id, "hubspotConnectorId": hubspot_connector_id},
    )
    logger.info(
        "real_estate_vertical_installed org_id=%s workflow_id=%s hubspot=%s",
        org_id,
        workflow_id,
        hubspot_connector_id,
    )
    return {
        "installed": True,
        "installedAt": now,
        "hubspotConnectorId": hubspot_connector_id,
        "listingWorkflowId": workflow_id,
        "listingCoordinatorAgentId": agents["listingCoordinatorAgentId"],
        "buyerAgentId": agents["buyerAgentId"],
    }
