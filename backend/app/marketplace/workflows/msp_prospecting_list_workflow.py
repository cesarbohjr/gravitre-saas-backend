"""MSP prospecting + list-building workflow (agents, tools, task assignments).

Replaces the legacy read-only NVD CVE demo workflow as the MSP pack's runnable
canvas workflow. Vulnerability knowledge packs remain as agent assignments.

Membership is deterministic invoke_tool (apollo.lists.add / hubspot.lists.add_contact),
not agent-only instructions — empty list shells must not "complete" via hope.
"""
from __future__ import annotations

from typing import Any

WORKFLOW_NAME = "MSP Prospecting & List Builder"
WORKFLOW_DESCRIPTION = (
    "Prospect Managed Service Providers: agent ICP brief → Apollo company/contact discovery "
    "→ qualify & assign list-build tasks → create Apollo + HubSpot lists → membership + notify. "
    "Requires connected Apollo and HubSpot; Clay enrichment optional when connected."
)
WORKFLOW_SLUG = "msp-prospecting-list-builder"

DEFAULT_APOLLO_LIST_NAME = "MSP Prospects"
DEFAULT_HUBSPOT_LIST_NAME = "MSPs"
DEFAULT_ORG_QUERY = "Managed Service Provider"
DEFAULT_PEOPLE_QUERY = "MSP owner OR managing partner OR VP operations"

SCOUT_AGENT_SLUG = "msp-prospecting-coordinator"
SCOUT_AGENT_NAME = "MSP Prospecting Coordinator"
SCOUT_AGENT_PURPOSE = (
    "Scouts MSP accounts, qualifies contacts, builds Apollo/HubSpot lists, and notifies on progress."
)
SCOUT_AGENT_ROLE = "Sales Development"
SCOUT_AGENT_DEPARTMENT = "Sales"
SCOUT_AGENT_SYSTEMS = ["apollo", "hubspot", "clay"]
SCOUT_AGENT_CAPABILITIES = [
    "prospecting",
    "list_building",
    "apollo_lists",
    "hubspot_lists",
    "enrichment",
]


def _invoke(
    step_id: str,
    name: str,
    action: str,
    *,
    connector: str,
    params: dict[str, Any] | None = None,
    param_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.marketplace.workflows.step_builders import invoke_step

    return invoke_step(
        step_id,
        name,
        action,
        connector=connector,
        params=params,
        param_sources=param_sources,
    )


def _agent_step(
    step_id: str,
    name: str,
    task: str,
    *,
    agent_slug: str = SCOUT_AGENT_SLUG,
    briefing_from_steps: bool = False,
    receiver_task: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "agent_seed": f"agent:{agent_slug}",
        "task": task,
        "assignment": True,
    }
    if briefing_from_steps:
        metadata["briefing_from_steps"] = True
    if receiver_task:
        metadata["receiver_task"] = receiver_task
    return {
        "id": step_id,
        "name": name,
        "type": "agent",
        "metadata": metadata,
    }


def build_msp_prospecting_list_workflow_steps() -> list[dict[str, Any]]:
    """Ordered canvas steps for MSP outbound list building."""
    icp_task = (
        "Assignment: open an MSP prospecting brief. Define ICP for Managed Service Providers "
        "(company size, geography, tech stack signals). Confirm target Apollo list name "
        f'"{DEFAULT_APOLLO_LIST_NAME}" and HubSpot list "{DEFAULT_HUBSPOT_LIST_NAME}". '
        "List the discovery queries to run next. Notify the operator that scouting has started."
    )
    qualify_task = (
        "Assignment: using prior Apollo organization + people search results, qualify the best "
        "MSP accounts and contacts (title fit, company relevance). Produce a short membership plan "
        "for the operator (who will be added by the next deterministic tool steps). "
        f'Set context for list create name="{DEFAULT_APOLLO_LIST_NAME}". '
        "Notify with discovery counts (companies found, contacts selected). "
        "Do not call apollo.lists.add or hubspot.lists.add_contact — those run as tool steps next."
    )
    notify_task = (
        "Assignment: using prior create + membership tool results, summarize Apollo list "
        f'"{DEFAULT_APOLLO_LIST_NAME}" and HubSpot list "{DEFAULT_HUBSPOT_LIST_NAME}" status '
        "(created vs already existed, contacts added counts). "
        "If Clay is connected and enrichment is needed, note it as a follow-on. "
        "Notify the operator that list-build membership steps finished and mark the assignment complete."
    )
    return [
        _agent_step(
            "msp_icp_brief",
            "Agent: MSP ICP & scouting assignment",
            icp_task,
        ),
        _invoke(
            "apollo_org_search",
            "Task: Find MSP companies (Apollo)",
            "apollo.organizations.search",
            connector="apollo",
            params={
                "q_organization_keyword_tags": DEFAULT_ORG_QUERY,
                "q_organization_name": "MSP",
                "per_page": 10,
            },
        ),
        _invoke(
            "apollo_people_search",
            "Task: Find MSP contacts (Apollo)",
            "apollo.people.search",
            connector="apollo",
            params={
                "q_keywords": DEFAULT_PEOPLE_QUERY,
                "per_page": 10,
            },
        ),
        _agent_step(
            "qualify_and_plan_list",
            "Agent: Qualify prospects & plan list membership",
            qualify_task,
            briefing_from_steps=True,
        ),
        _invoke(
            "apollo_list_create",
            "Task: Create Apollo list (MSP Prospects)",
            "apollo.lists.create",
            connector="apollo",
            params={"name": DEFAULT_APOLLO_LIST_NAME, "modality": "contacts"},
        ),
        # Deterministic membership — not agent-only instructions.
        _invoke(
            "apollo_list_add",
            "Task: Add contacts to Apollo list",
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
        _invoke(
            "hubspot_list_create",
            "Task: Create HubSpot list (MSPs)",
            "hubspot.lists.create",
            connector="hubspot",
            params={"name": DEFAULT_HUBSPOT_LIST_NAME},
        ),
        _invoke(
            "hubspot_contact_create",
            "Task: Create HubSpot contact from Apollo lead",
            "hubspot.contacts.create",
            connector="hubspot",
            param_sources={
                "properties": {
                    "from_step": "apollo_people_search",
                    "path": ["hubspot_contact_properties"],
                },
            },
        ),
        _invoke(
            "hubspot_list_add",
            "Task: Add contact to HubSpot list",
            "hubspot.lists.add_contact",
            connector="hubspot",
            param_sources={
                "list_id": {
                    "from_step": "hubspot_list_create",
                    "path": ["list_id"],
                },
                "contact_id": {
                    "from_step": "hubspot_contact_create",
                    "path": ["contact_id"],
                },
            },
        ),
        _agent_step(
            "hubspot_sync_and_notify",
            "Agent: Summarize list build + complete assignment",
            notify_task,
            briefing_from_steps=True,
        ),
    ]
