"""MSP Prospects → Clay enrichment → HubSpot list sync workflow definition.

Reusable by marketplace seed catalog and Prospecting intelligence pack install.

Apollo list membership and HubSpot list membership use deterministic invoke_tool
steps. Agents prepare Clay batches and summarize — they do not own membership writes.
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
DEFAULT_PEOPLE_QUERY = "MSP owner OR managing partner OR VP operations"

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
    "Orchestrates Apollo list population/export, Clay enrichment, and HubSpot static list membership."
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
    params: dict[str, Any] | None = None,
    param_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    step: dict[str, Any] = {
        "id": step_id,
        "name": name,
        "type": "invoke_tool",
        "config": {"action": action},
        "requires_connector": connector,
    }
    if params:
        step["config"]["params"] = params
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
    """Ordered steps: Apollo membership → Clay enrich → HubSpot CRM + list membership."""
    clay_prep_task = (
        f'Using apollo.lists.list / contacts.search / people.search / lists.add results for '
        f'"{DEFAULT_APOLLO_LIST_NAME}" (or install variable APOLLO_LIST_NAME): '
        "Extract contact records (email, name, company, title, LinkedIn URL) and prepare a "
        "Clay-ready records batch for enrichment. Set $clay_records for the next step. "
        "Do not call apollo.lists.add or hubspot.lists.add_contact — membership is handled "
        "by dedicated tool steps."
    )
    summarize_task = (
        f'Using clay.crm.sync and hubspot.lists.add_contact results for list '
        f'"{DEFAULT_HUBSPOT_LIST_NAME}" (list_id from HUBSPOT_LIST_ID): '
        "Summarize synced CRM contacts, list membership adds, and any skipped/errors. "
        "Notify the operator that enrichment → HubSpot membership finished."
    )
    return [
        _invoke(
            "apollo_lists",
            "List Apollo contact lists",
            "apollo.lists.list",
            connector="apollo",
        ),
        _invoke(
            "apollo_contacts_search",
            "Search Apollo contacts in MSP Prospects",
            "apollo.contacts.search",
            connector="apollo",
            param_sources={"list_name": DEFAULT_APOLLO_LIST_NAME},
        ),
        # Always prospect + add so empty shells get real membership (not agent hope).
        _invoke(
            "apollo_people_search",
            "Prospect MSP contacts (Apollo people search)",
            "apollo.people.search",
            connector="apollo",
            params={
                "q_keywords": DEFAULT_PEOPLE_QUERY,
                "per_page": 10,
            },
        ),
        _invoke(
            "apollo_list_add",
            "Add prospects to Apollo list",
            "apollo.lists.add",
            connector="apollo",
            params={
                "label_names": [DEFAULT_APOLLO_LIST_NAME],
                "modality": "contacts",
            },
            param_sources={
                "entity_ids": {
                    "from_step": "apollo_people_search",
                    "path": ["entity_ids"],
                },
            },
        ),
        _agent_step(
            "prepare_clay_batch",
            "Prepare Clay enrichment batch",
            clay_prep_task,
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
        _invoke(
            "hubspot_list_add",
            "Add synced contact to HubSpot static list",
            "hubspot.lists.add_contact",
            connector="hubspot",
            param_sources={
                "list_id": "$HUBSPOT_LIST_ID",
                "contact_id": {
                    "from_step": "hubspot_crm_sync",
                    "path": ["primary_contact_id"],
                },
            },
        ),
        _agent_step(
            "summarize_enrichment",
            "Summarize enrichment + HubSpot membership",
            summarize_task,
            briefing_from_steps=True,
        ),
    ]
