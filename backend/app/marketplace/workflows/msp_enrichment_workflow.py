"""MSP Prospects → Clay enrichment → HubSpot list sync workflow definition.

Reusable by marketplace seed catalog and Prospecting intelligence pack install.
"""
from __future__ import annotations

from typing import Any

WORKFLOW_NAME = "MSP Prospects Clay Enrichment → HubSpot Sync"
WORKFLOW_DESCRIPTION = (
    "Locate the existing Apollo contact list, enrich contacts in Clay, sync to HubSpot CRM, "
    "and add contacts to an existing HubSpot static list. Requires connected Apollo, Clay, "
    "and HubSpot connectors."
)
WORKFLOW_SLUG = "msp-prospects-clay-hubspot-enrichment"

DEFAULT_APOLLO_LIST_NAME = "MSP Prospects"
DEFAULT_HUBSPOT_LIST_NAME = "MSPs"

INSTALL_VARIABLES: list[dict[str, Any]] = [
    {
        "key": "APOLLO_LIST_NAME",
        "label": "Apollo contact list name",
        "required": False,
        "default": DEFAULT_APOLLO_LIST_NAME,
        "description": 'Existing Apollo list to enrich (default "MSP Prospects").',
    },
    {
        "key": "HUBSPOT_LIST_ID",
        "label": "HubSpot static list ID",
        "required": True,
        "description": (
            'Numeric list ID for the existing HubSpot static list (e.g. "MSPs"). '
            "Find it in HubSpot → Lists → open the list → copy the ID from the URL."
        ),
    },
    {
        "key": "HUBSPOT_LIST_NAME",
        "label": "HubSpot static list name (reference only)",
        "required": False,
        "default": DEFAULT_HUBSPOT_LIST_NAME,
        "description": 'Human-readable list label for agent steps (default "MSPs").',
    },
]

AGENT_SLUG = "lead-enrichment-coordinator"
AGENT_NAME = "Lead Enrichment Coordinator"
AGENT_PURPOSE = (
    "Orchestrates Apollo list export, Clay enrichment, and HubSpot static list membership."
)
AGENT_ROLE = "Sales Development"
AGENT_DEPARTMENT = "Sales"
AGENT_PERSONA = "SALES"
AGENT_SYSTEMS = ["apollo", "clay", "hubspot"]
AGENT_CAPABILITIES = ["enrichment", "list_sync", "apollo_lists", "hubspot_lists"]


def _invoke(
    step_id: str,
    name: str,
    action: str,
    *,
    connector: str,
    param_sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "id": step_id,
        "name": name,
        "type": "invoke_tool",
        "config": {"action": action},
        "requires_connector": connector,
    }
    if param_sources:
        step["config"]["param_sources"] = param_sources
    return step


def _agent_step(
    step_id: str,
    name: str,
    task: str,
    *,
    next_task: str | None = None,
    briefing_from_steps: bool = False,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "agent_seed": f"agent:{AGENT_SLUG}",
        "task": task,
    }
    if next_task:
        metadata["receiver_task"] = next_task
    if briefing_from_steps:
        metadata["briefing_from_steps"] = True
    return {
        "id": step_id,
        "name": name,
        "type": "agent",
        "metadata": metadata,
    }


def build_msp_enrichment_workflow_steps() -> list[dict[str, Any]]:
    """Ordered steps: Apollo list → Clay enrich → HubSpot CRM + list membership."""
    apollo_list_task = (
        f'From the Apollo lists output, locate the existing contact list named '
        f'"{DEFAULT_APOLLO_LIST_NAME}" (or the install variable APOLLO_LIST_NAME). '
        "Extract contact records with email, name, company, title, and LinkedIn URL. "
        "Prepare a Clay-ready records batch for enrichment."
    )
    hubspot_list_task = (
        f'Using the HubSpot contacts created by clay.crm.sync, add each contact to the '
        f'existing HubSpot static list "{DEFAULT_HUBSPOT_LIST_NAME}" via hubspot.lists.add_contact '
        "(list_id from install variable HUBSPOT_LIST_ID). Skip records missing contact_id. "
        "Summarize added and skipped counts."
    )
    return [
        _invoke(
            "apollo_lists",
            "List Apollo contact lists",
            "apollo.lists.list",
            connector="apollo",
        ),
        _agent_step(
            "prepare_clay_batch",
            "Prepare Clay enrichment batch",
            apollo_list_task,
            briefing_from_steps=True,
        ),
        _invoke(
            "clay_push",
            "Push leads to Clay",
            "clay.leads.push",
            connector="clay",
            param_sources={"records": "$clay_records"},
        ),
        _invoke(
            "clay_outputs",
            "Pull Clay enriched outputs",
            "clay.workflows.output.get",
            connector="clay",
        ),
        _invoke(
            "hubspot_crm_sync",
            "Sync enriched records to HubSpot CRM",
            "clay.crm.sync",
            connector="clay",
            param_sources={
                "records": "$enriched_records",
                "crm_connector_id": "$hubspot_connector_id",
                "crm": "hubspot",
            },
        ),
        _agent_step(
            "hubspot_list_membership",
            "Add contacts to HubSpot static list",
            hubspot_list_task,
            briefing_from_steps=True,
        ),
    ]
