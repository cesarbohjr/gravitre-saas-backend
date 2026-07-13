"""Central registry of agent-facing tools mapped to invoke_tool actions (STA-159 / AI-025).

Bridges LLM tool calls (OpenAI function format) to the unified connector layer in
``tool_service.invoke_tool``. ReAct and AgentIntelligence use this module.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.connectors.repository import list_connectors
from app.core.logging import get_logger
from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import ToolContext, ToolError, ToolNotFoundError

logger = get_logger(__name__)

ParamMapper = Callable[[dict[str, Any]], dict[str, Any]]

from app.connectors.constants import is_connector_usable


def _hubspot_search_from_query(args: dict[str, Any]) -> dict[str, Any]:
    """Map a simple text query to HubSpot filter_groups, or list recent contacts."""
    limit = int(args.get("limit") or 10)
    if args.get("list_all") or args.get("listAll"):
        return {"list_all": True, "limit": limit}
    query = str(args.get("query") or "").strip()
    if not query:
        return {"list_all": True, "limit": limit}
    return {
        "filter_groups": [
            {
                "filters": [
                    {
                        "propertyName": "email",
                        "operator": "CONTAINS_TOKEN",
                        "value": query,
                    }
                ]
            },
            {
                "filters": [
                    {
                        "propertyName": "firstname",
                        "operator": "CONTAINS_TOKEN",
                        "value": query,
                    }
                ]
            },
            {
                "filters": [
                    {
                        "propertyName": "lastname",
                        "operator": "CONTAINS_TOKEN",
                        "value": query,
                    }
                ]
            },
        ],
        "limit": limit,
    }


def _hubspot_contact_create(args: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    if args.get("properties") and isinstance(args["properties"], dict):
        properties.update(args["properties"])
    for src, dest in (
        ("email", "email"),
        ("firstname", "firstname"),
        ("lastname", "lastname"),
        ("company", "company"),
        ("phone", "phone"),
    ):
        if args.get(src):
            properties[dest] = args[src]
    if not properties:
        raise ValueError("At least one contact property is required")
    return {"properties": properties}


def _hubspot_deal_update(args: dict[str, Any]) -> dict[str, Any]:
    deal_id = args.get("deal_id")
    if not deal_id:
        raise ValueError("deal_id is required")
    properties: dict[str, Any] = {}
    if args.get("properties") and isinstance(args["properties"], dict):
        properties.update(args["properties"])
    if args.get("stage"):
        properties["dealstage"] = args["stage"]
    if args.get("amount") is not None:
        properties["amount"] = str(args["amount"])
    if args.get("close_date"):
        properties["closedate"] = args["close_date"]
    if not properties:
        raise ValueError("At least one deal property is required")
    return {"deal_id": deal_id, "properties": properties}


def _hubspot_note_activity(args: dict[str, Any]) -> dict[str, Any]:
    body = args.get("body") or args.get("note") or args.get("message")
    if not body:
        raise ValueError("body is required")
    mapped: dict[str, Any] = {"body": body}
    if args.get("contact_id"):
        mapped["contact_id"] = args["contact_id"]
    if args.get("deal_id"):
        mapped["deal_id"] = args["deal_id"]
    return mapped


def _salesforce_soql_query(args: dict[str, Any]) -> dict[str, Any]:
    soql = args.get("soql")
    if not soql:
        raise ValueError("soql is required")
    return {"soql": soql}


def _salesforce_update_record(args: dict[str, Any]) -> dict[str, Any]:
    object_type = str(args.get("object_type") or "Lead").lower()
    record_id = args.get("record_id")
    fields = args.get("fields")
    if not record_id:
        raise ValueError("record_id is required")
    if not isinstance(fields, dict) or not fields:
        raise ValueError("fields object is required")
    if object_type in {"lead", "leads"}:
        return {"lead_id": record_id, "fields": fields, "_object_type": object_type}
    if object_type in {"opportunity", "opportunities", "opp"}:
        return {"opportunity_id": record_id, "fields": fields, "_object_type": object_type}
    if object_type in {"account", "accounts"}:
        return {"account_id": record_id, "fields": fields, "_object_type": object_type}
    raise ValueError(f"Unsupported object_type for update: {object_type}")


def _slack_message(args: dict[str, Any]) -> dict[str, Any]:
    channel = args.get("channel")
    message = args.get("message")
    if not channel or not message:
        raise ValueError("channel and message are required")
    mapped: dict[str, Any] = {"channel": channel, "message": message}
    if args.get("blocks"):
        mapped["blocks"] = args["blocks"]
    return mapped


def _parse_github_repo(args: dict[str, Any]) -> tuple[str, str]:
    """Parse owner/repo from repo string or explicit owner + repo fields."""
    owner = args.get("owner")
    repo = args.get("repo")
    if owner and repo and "/" not in str(repo):
        return str(owner), str(repo)
    combined = str(repo or "")
    if "/" in combined:
        parts = combined.split("/", 1)
        return parts[0], parts[1]
    if owner:
        return str(owner), str(repo or "")
    raise ValueError("repo must be owner/repo or provide owner and repo")


def _dict_from_github_repo(args: dict[str, Any]) -> dict[str, str]:
    owner, repo = _parse_github_repo(args)
    return {"owner": owner, "repo": repo}


def _github_issue_create(args: dict[str, Any]) -> dict[str, Any]:
    title = args.get("title")
    if not title:
        raise ValueError("title is required")
    owner, repo = _parse_github_repo(args)
    mapped: dict[str, Any] = {"owner": owner, "repo": repo, "title": title}
    if args.get("body"):
        mapped["body"] = args["body"]
    if args.get("labels"):
        mapped["labels"] = args["labels"]
    if args.get("assignees"):
        mapped["assignees"] = args["assignees"]
    return mapped


def _jira_ticket_create(args: dict[str, Any]) -> dict[str, Any]:
    project = args.get("project") or args.get("project_key")
    summary = args.get("summary")
    if not project or not summary:
        raise ValueError("project and summary are required")
    mapped: dict[str, Any] = {
        "project_key": project,
        "summary": summary,
    }
    if args.get("description"):
        mapped["description"] = args["description"]
    if args.get("issue_type"):
        mapped["issue_type"] = args["issue_type"]
    if args.get("priority"):
        mapped["priority"] = args["priority"]
    if args.get("assignee"):
        mapped["assignee"] = args["assignee"]
    return mapped


def _zendesk_ticket_update(args: dict[str, Any]) -> dict[str, Any]:
    ticket_id = args.get("ticket_id")
    if not ticket_id:
        raise ValueError("ticket_id is required")
    mapped: dict[str, Any] = {"ticket_id": ticket_id}
    if args.get("status"):
        mapped["status"] = args["status"]
    if args.get("priority"):
        mapped["priority"] = args["priority"]
    if args.get("comment"):
        mapped["comment"] = args["comment"]
    if args.get("assignee_id"):
        mapped["assignee_id"] = args["assignee_id"]
    return mapped


@dataclass(frozen=True)
class AgentToolSpec:
    """LLM-visible tool mapped to a canonical invoke_tool action."""

    name: str
    description: str
    parameters: dict[str, Any]
    invoke_action: str
    integration: str
    map_params: ParamMapper | None = None
    always_available: bool = False

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _build_agent_tool_specs() -> dict[str, AgentToolSpec]:
    """Register agent tools that map to implemented invoke_tool actions."""
    specs: list[AgentToolSpec] = [
        AgentToolSpec(
            name="hubspot_search_contacts",
            description=(
                "Search HubSpot CRM contacts by name, email, company, or keyword. "
                "Use when the agent needs to find or look up customer or prospect records."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
            invoke_action="hubspot.contacts.search",
            integration="hubspot",
            map_params=_hubspot_search_from_query,
        ),
        AgentToolSpec(
            name="hubspot_update_deal",
            description="Update a HubSpot deal's stage, amount, close date, or other properties.",
            parameters={
                "type": "object",
                "properties": {
                    "deal_id": {"type": "string"},
                    "stage": {"type": "string"},
                    "amount": {"type": "number"},
                    "close_date": {"type": "string"},
                    "properties": {"type": "object"},
                },
                "required": ["deal_id"],
            },
            invoke_action="hubspot.deals.update",
            integration="hubspot",
            map_params=_hubspot_deal_update,
        ),
        AgentToolSpec(
            name="hubspot_create_contact",
            description="Create a new contact in HubSpot CRM.",
            parameters={
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "firstname": {"type": "string"},
                    "lastname": {"type": "string"},
                    "company": {"type": "string"},
                    "phone": {"type": "string"},
                    "properties": {"type": "object"},
                },
                "required": ["email"],
            },
            invoke_action="hubspot.contacts.create",
            integration="hubspot",
            map_params=_hubspot_contact_create,
        ),
        AgentToolSpec(
            name="hubspot_log_activity",
            description="Log a call, email, meeting, or note on a HubSpot contact or deal.",
            parameters={
                "type": "object",
                "properties": {
                    "body": {"type": "string"},
                    "contact_id": {"type": "string"},
                    "deal_id": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["call", "email", "meeting", "note"],
                    },
                },
                "required": ["body"],
            },
            invoke_action="hubspot.notes.create",
            integration="hubspot",
            map_params=_hubspot_note_activity,
        ),
        AgentToolSpec(
            name="salesforce_query",
            description=(
                "Query Salesforce using SOQL. Use for leads, opportunities, accounts, "
                "contacts, cases, or custom objects."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "soql": {"type": "string", "description": "SOQL query string"},
                },
                "required": ["soql"],
            },
            invoke_action="salesforce.leads.search",
            integration="salesforce",
            map_params=_salesforce_soql_query,
        ),
        AgentToolSpec(
            name="salesforce_update_record",
            description="Update a Salesforce record by ID (Lead, Opportunity, or Account).",
            parameters={
                "type": "object",
                "properties": {
                    "object_type": {"type": "string"},
                    "record_id": {"type": "string"},
                    "fields": {"type": "object"},
                },
                "required": ["object_type", "record_id", "fields"],
            },
            invoke_action="salesforce.leads.update",
            integration="salesforce",
            map_params=_salesforce_update_record,
        ),
        AgentToolSpec(
            name="slack_send_message",
            description=(
                "Send a message to a Slack channel or user. Use for notifications, "
                "alerts, status updates, or handoffs that require human awareness."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"},
                    "blocks": {"type": "array"},
                },
                "required": ["channel", "message"],
            },
            invoke_action="slack.post_message",
            integration="slack",
            map_params=_slack_message,
        ),
        AgentToolSpec(
            name="github_create_issue",
            description="Create a GitHub issue in a repository.",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "owner/repo"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "assignees": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["repo", "title"],
            },
            invoke_action="github.issues.create",
            integration="github",
            map_params=_github_issue_create,
        ),
        AgentToolSpec(
            name="github_search_issues",
            description="Search GitHub pull requests in a repository (read-only discovery).",
            parameters={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "owner/repo"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"]},
                    "limit": {"type": "integer"},
                },
                "required": ["repo"],
            },
            invoke_action="github.pulls.list",
            integration="github",
            map_params=lambda args: {
                **_dict_from_github_repo(args),
                **{k: v for k, v in args.items() if k in ("state", "limit")},
            },
        ),
        AgentToolSpec(
            name="jira_create_ticket",
            description="Create a Jira issue or ticket.",
            parameters={
                "type": "object",
                "properties": {
                    "project": {"type": "string"},
                    "summary": {"type": "string"},
                    "description": {"type": "string"},
                    "issue_type": {"type": "string"},
                    "priority": {"type": "string"},
                    "assignee": {"type": "string"},
                },
                "required": ["project", "summary"],
            },
            invoke_action="jira.issues.create",
            integration="jira",
            map_params=_jira_ticket_create,
        ),
        AgentToolSpec(
            name="jira_search_issues",
            description="Search Jira issues using JQL or project/status filters.",
            parameters={
                "type": "object",
                "properties": {
                    "jql": {"type": "string"},
                    "project_key": {"type": "string"},
                    "status": {"type": "string"},
                    "assignee": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
            invoke_action="jira.issues.search",
            integration="jira",
        ),
        AgentToolSpec(
            name="pagerduty_list_incidents",
            description="List recent PagerDuty incidents for triage and on-call response.",
            parameters={
                "type": "object",
                "properties": {
                    "statuses": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
            },
            invoke_action="pagerduty.incidents.list",
            integration="pagerduty",
        ),
        AgentToolSpec(
            name="quickbooks_list_invoices",
            description="List invoices from QuickBooks (read-only).",
            parameters={
                "type": "object",
                "properties": {"limit": {"type": "integer"}},
            },
            invoke_action="quickbooks.invoices.list",
            integration="quickbooks",
        ),
        AgentToolSpec(
            name="stripe_list_invoices",
            description="List Stripe invoices for a customer or account (read-only).",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer"},
                    "customer_id": {"type": "string"},
                },
            },
            invoke_action="stripe.invoices.list",
            integration="stripe",
        ),
        AgentToolSpec(
            name="zendesk_get_ticket",
            description="Get a Zendesk support ticket by ID.",
            parameters={
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
            },
            invoke_action="zendesk.tickets.get",
            integration="zendesk",
        ),
        AgentToolSpec(
            name="zendesk_update_ticket",
            description="Update a Zendesk ticket status, priority, assignee, or add a comment.",
            parameters={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "status": {"type": "string"},
                    "priority": {"type": "string"},
                    "comment": {"type": "string"},
                    "assignee_id": {"type": "string"},
                },
                "required": ["ticket_id"],
            },
            invoke_action="zendesk.tickets.update",
            integration="zendesk",
            map_params=_zendesk_ticket_update,
        ),
        AgentToolSpec(
            name="fred_get_series",
            description=(
                "Fetch a FRED macro time-series observation (Gravitree-managed). "
                "Use for US GDP, unemployment, inflation, and other FRED series_id values."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "series_id": {
                        "type": "string",
                        "description": "FRED series ID, e.g. GDP, UNRATE, CPIAUCSL",
                    },
                },
                "required": ["series_id"],
            },
            invoke_action="fred.series.get",
            integration="fred",
        ),
        AgentToolSpec(
            name="nvd_get_cve",
            description=(
                "Look up a CVE in the NIST NVD catalog (Gravitree-managed). "
                "Use when the agent needs vulnerability details for a CVE id."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "cve_id": {
                        "type": "string",
                        "description": "CVE identifier, e.g. CVE-2024-21762",
                    },
                },
                "required": ["cve_id"],
            },
            invoke_action="nvd.cve.get",
            integration="nvd",
        ),
        AgentToolSpec(
            name="cisa_kev_get_feed",
            description=(
                "Fetch a sample of the CISA Known Exploited Vulnerabilities catalog "
                "(Gravitree-managed public feed)."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            invoke_action="cisa_kev.feed.get",
            integration="cisa_kev",
        ),
        AgentToolSpec(
            name="sec_edgar_search_filings",
            description=(
                "Search SEC EDGAR for recent company filings (10-K/10-Q/8-K). "
                "Gravitree-managed; requires SEC_USER_AGENT on the platform."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Company name or ticker, e.g. Microsoft",
                    },
                },
                "required": ["query"],
            },
            invoke_action="sec_edgar.filings.search",
            integration="sec_edgar",
        ),
        AgentToolSpec(
            name="web_search",
            description=(
                "Search the web for current information not in the knowledge base. "
                "Use when internal data is insufficient or the question needs real-time external facts."
            ),
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            invoke_action="web.search",
            integration="web",
            always_available=True,
        ),
        AgentToolSpec(
            name="browser_agent_read",
            description=(
                "Read and extract text from a public web page when no native connector API exists. "
                "Use for API gaps — provide the authenticated session URL the user shares."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "HTTPS URL to read."},
                    "selector": {
                        "type": "string",
                        "description": "Optional CSS selector hint (read-only mode returns full page text).",
                    },
                },
                "required": ["url"],
            },
            invoke_action="browser_agent.read",
            integration="browser",
            always_available=True,
        ),
        AgentToolSpec(
            name="browser_agent_interact",
            description=(
                "Perform approved UI automation (click/fill) when connector APIs cannot complete the task. "
                "Requires human approval — returns pending_approval without approval_id."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "approval_id": {"type": "string", "description": "Approved action id from Approvals queue."},
                    "actions": {
                        "type": "array",
                        "description": "Steps: {type: click|fill|wait, selector, value?, ms?}",
                        "items": {"type": "object"},
                    },
                },
                "required": ["url", "actions"],
            },
            invoke_action="browser_agent.interact",
            integration="browser",
            always_available=True,
        ),
        AgentToolSpec(
            name="assistant_agent_status",
            description="List agents and their current status for this organization.",
            parameters={"type": "object", "properties": {"agentId": {"type": "string"}}},
            invoke_action="assistant.agent_status",
            integration="platform",
            always_available=False,
        ),
        AgentToolSpec(
            name="assistant_connector_status",
            description="List connectors and health for this organization.",
            parameters={"type": "object", "properties": {}},
            invoke_action="assistant.connector_status",
            integration="platform",
            always_available=False,
        ),
        AgentToolSpec(
            name="assistant_workflow_runs",
            description="List recent workflow runs, optionally filtered by status.",
            parameters={
                "type": "object",
                "properties": {"limit": {"type": "integer"}, "status": {"type": "string"}},
            },
            invoke_action="assistant.workflow_runs",
            integration="platform",
            always_available=False,
        ),
        AgentToolSpec(
            name="assistant_analytics",
            description="Load organization analytics snapshot and recent workflow throughput.",
            parameters={"type": "object", "properties": {}},
            invoke_action="assistant.analytics",
            integration="platform",
            always_available=False,
        ),
        AgentToolSpec(
            name="assistant_generate_document",
            description="Generate a markdown document on a topic.",
            parameters={"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
            invoke_action="assistant.generate_document",
            integration="platform",
            always_available=False,
        ),
        AgentToolSpec(
            name="assistant_run_agent_task",
            description="Run a task using a configured agent.",
            parameters={
                "type": "object",
                "properties": {"task": {"type": "string"}, "agentId": {"type": "string"}},
                "required": ["task"],
            },
            invoke_action="assistant.run_agent_task",
            integration="platform",
            always_available=False,
        ),
        AgentToolSpec(
            name="assistant_create_workflow",
            description="Create a draft workflow from a natural-language goal.",
            parameters={"type": "object", "properties": {"name": {"type": "string"}, "goal": {"type": "string"}}},
            invoke_action="assistant.create_workflow",
            integration="platform",
            always_available=False,
        ),
        AgentToolSpec(
            name="assistant_execute_workflow",
            description="Execute an existing workflow by name or id.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}, "workflowId": {"type": "string"}},
                "required": ["query"],
            },
            invoke_action="assistant.execute_workflow",
            integration="platform",
            always_available=False,
        ),
        AgentToolSpec(
            name="assistant_dependency_impact",
            description=(
                "Report what depends on a connector, agent, or workflow and what would break if removed. "
                "Use for questions like 'what happens if we disconnect HubSpot?'"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "entity_type": {"type": "string", "enum": ["connector", "agent", "workflow"]},
                    "entity_id": {"type": "string"},
                },
            },
            invoke_action="assistant.dependency_impact",
            integration="platform",
            always_available=False,
        ),
    ]
    return {spec.name: spec for spec in specs}


_SALESFORCE_UPDATE_ACTIONS: dict[str, str] = {
    "lead": "salesforce.leads.update",
    "leads": "salesforce.leads.update",
    "opportunity": "salesforce.opportunities.update",
    "opportunities": "salesforce.opportunities.update",
    "opp": "salesforce.opportunities.update",
    "account": "salesforce.accounts.update",
    "accounts": "salesforce.accounts.update",
}


class ToolRegistry:
    """
    Central registry of LLM tool definitions backed by invoke_tool.

    Agents receive tools that are both permitted for the agent and connected
    for the organization.
    """

    def __init__(self) -> None:
        from app.services.chat_tool_bridge import build_dynamic_chat_tool_specs

        dynamic = build_dynamic_chat_tool_specs()
        static = _build_agent_tool_specs()
        self._static_specs = static
        self._specs = {**dynamic, **static}
        self._registered = set(list_registered_actions())

    def preferred_static_tool_name(self, invoke_action: str, integration: str) -> str | None:
        """Return curated static tool name for an invoke_tool action when one exists."""
        for name, spec in self._static_specs.items():
            if spec.invoke_action == invoke_action and spec.integration == integration:
                return name
        return None

    def list_tool_names(self) -> list[str]:
        """All agent tool names defined in this registry."""
        return sorted(self._specs.keys())

    def get_spec(self, tool_name: str) -> AgentToolSpec | None:
        return self._specs.get(tool_name)

    def resolve_invoke_action(self, spec: AgentToolSpec, mapped_params: dict[str, Any]) -> str:
        """Resolve invoke_tool action; salesforce_update_record varies by object type."""
        if spec.name == "salesforce_update_record":
            object_type = str(mapped_params.get("_object_type") or "lead").lower()
            action = _SALESFORCE_UPDATE_ACTIONS.get(object_type)
            if not action:
                raise ValueError(f"Unsupported Salesforce object_type: {object_type}")
            return action
        return spec.invoke_action

    @staticmethod
    def list_connected_integrations(
        client: Any,
        org_id: str,
        environment_name: str = "production",
        *,
        force_live: bool = True,
        action_key: str | None = None,
    ) -> list[str]:
        """Return connector types with an active, executable connection for the org."""
        from app.connectors.connector_availability_service import list_executable_integrations

        return list_executable_integrations(
            client,
            org_id,
            get_settings(),
            environment_name=environment_name,
            force_live=force_live,
            action_key=action_key,
        )

    async def enrich_connected_integrations(
        self,
        client: Any,
        org_id: str,
        connected_integrations: list[str],
    ) -> list[str]:
        """Append synthetic integrations for MCP and browser gap recovery."""
        enriched = list(connected_integrations)
        seen = {str(c).strip().lower() for c in enriched}
        from app.services.mcp_client_service import get_mcp_client_service

        mcp_tools = await get_mcp_client_service().get_enabled_tools_for_org(org_id)
        if mcp_tools and "mcp" not in seen:
            enriched.append("mcp")
            seen.add("mcp")
        settings = get_settings()
        if getattr(settings, "browser_agent_enabled", True) and "browser" not in seen:
            enriched.append("browser")
        return enriched

    def _permitted(self, spec: AgentToolSpec, permitted_tools: list[str]) -> bool:
        if spec.always_available:
            return True
        if not permitted_tools:
            return True
        normalized = {str(t).strip().lower() for t in permitted_tools}
        if "all" in normalized or "*" in normalized:
            return True
        if spec.name in normalized:
            return True
        if spec.integration in normalized:
            return True
        prefix = spec.name.split("_", 1)[0]
        if prefix in normalized:
            return True
        return False

    def _connected(self, spec: AgentToolSpec, connected_integrations: list[str]) -> bool:
        if spec.always_available:
            return True
        # Phase 3: gravitree-managed sources use platform keys — available without tenant OAuth
        if spec.integration in {"fred", "nvd"}:
            return True
        connected = {str(c).strip().lower() for c in connected_integrations}
        return spec.integration in connected

    def _action_implemented(self, spec: AgentToolSpec, invoke_action: str) -> bool:
        if spec.always_available:
            return True
        if spec.name.startswith("assistant_"):
            return True
        return invoke_action in self._registered

    def get_tools_for_agent(
        self,
        permitted_tools: list[str],
        connected_integrations: list[str],
    ) -> list[dict[str, Any]]:
        """
        Return OpenAI-format tool definitions for tools that are permitted,
        connected, and backed by invoke_tool (except always_available stubs).
        """
        tools: list[dict[str, Any]] = []
        for spec in self._specs.values():
            if not self._permitted(spec, permitted_tools):
                continue
            if not self._connected(spec, connected_integrations):
                continue
            invoke_action = spec.invoke_action
            if spec.name == "salesforce_update_record":
                invoke_action = "salesforce.leads.update"
            if not self._action_implemented(spec, invoke_action):
                continue
            tools.append(spec.to_openai_tool())
        return tools

    async def get_available_tools(
        self,
        org_id: str,
        permitted_tools: list[str],
        connected_integrations: list[str],
    ) -> list[dict[str, Any]]:
        """Native connector tools plus org MCP tools (native names win on collision)."""
        native_tools = self.get_tools_for_agent(permitted_tools, connected_integrations)
        from app.services.mcp_client_service import get_mcp_client_service

        mcp_tools = await get_mcp_client_service().get_enabled_tools_for_org(org_id)
        native_names = {str(tool.get("function", {}).get("name") or tool.get("name") or "") for tool in native_tools}
        filtered_mcp: list[dict[str, Any]] = []
        for tool in mcp_tools:
            name = str(tool.get("name") or "")
            if not name or name in native_names:
                continue
            filtered_mcp.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": str(tool.get("description") or "MCP tool"),
                        "parameters": tool.get("input_schema")
                        if isinstance(tool.get("input_schema"), dict) and tool.get("input_schema")
                        else {"type": "object", "properties": tool.get("parameters") or {}},
                    },
                    "mcp_tool_id": tool.get("mcp_tool_id"),
                    "capability_tier": tool.get("capability_tier"),
                }
            )
        return native_tools + filtered_mcp

    def get_handler(self, tool_name: str) -> Callable[..., Any] | None:
        """Return async handler for a tool name, or None if unknown."""
        if tool_name in self._specs or tool_name.startswith("mcp_"):
            return self.execute_tool
        return None

    async def _execute_mcp_tool(
        self,
        ctx: ToolContext,
        tool_name: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        from app.services.mcp_client_service import get_mcp_client_service

        service = get_mcp_client_service(ctx.settings)
        tools = await service.get_enabled_tools_for_org(ctx.org_id)
        tool_id = None
        for row in tools:
            if str(row.get("name") or "") == tool_name:
                tool_id = str(row.get("mcp_tool_id") or "")
                break
        if not tool_id:
            return {"success": False, "tool": tool_name, "error": "MCP tool not registered for org"}
        approval_id = str(args.pop("approval_id", "") or args.pop("approvalId", "") or "") or None
        payload = await service.execute_tool(
            tool_id,
            ctx.org_id,
            args,
            agent_id=ctx.agent_id,
            workflow_run_id=ctx.run_id,
            approval_id=approval_id,
        )
        if payload.get("status") == "pending_approval":
            return {
                "success": False,
                "tool": tool_name,
                "pending_approval": True,
                "approval_id": payload.get("approval_id"),
                "message": payload.get("message"),
            }
        if payload.get("status") == "completed":
            return {
                "success": True,
                "tool": tool_name,
                "result": payload.get("result"),
                "latency_ms": payload.get("latency_ms"),
            }
        return {
            "success": False,
            "tool": tool_name,
            "error": payload.get("error") or "MCP tool execution failed",
        }

    async def execute_tool(
        self,
        *,
        ctx: ToolContext,
        tool_name: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute an agent tool call via invoke_tool.

        Returns a normalized dict suitable for injection into the LLM as a tool result.
        """
        spec = self._specs.get(tool_name)
        if not spec and tool_name.startswith("mcp_"):
            return await self._execute_mcp_tool(ctx, tool_name, args or {})
        if not spec:
            return {"success": False, "error": f"Unknown tool: {tool_name}", "tool": tool_name}

        if spec.always_available and tool_name == "browser_agent_read":
            from app.services.browser_agent_service import BrowserAgentError, browser_agent_read

            url = str((args or {}).get("url") or "").strip()
            if not url:
                return {"success": False, "tool": tool_name, "error": "Missing required 'url' argument"}
            if not getattr(ctx.settings, "browser_agent_enabled", True):
                return {
                    "success": False,
                    "tool": tool_name,
                    "error": "Browser agent is disabled (BROWSER_AGENT_ENABLED=false).",
                }
            try:
                payload = await browser_agent_read(
                    url,
                    settings=ctx.settings,
                    selector=str((args or {}).get("selector") or "") or None,
                )
            except BrowserAgentError as exc:
                return {"success": False, "tool": tool_name, "error": str(exc), "error_code": exc.code}
            except Exception as exc:  # noqa: BLE001
                logger.exception("browser_agent_read_failed url=%s", url[:120])
                return {"success": False, "tool": tool_name, "error": str(exc)}
            return {"success": True, "tool": tool_name, "result": payload}

        if spec.always_available and tool_name == "browser_agent_interact":
            from app.services.browser_agent_service import BrowserAgentError, browser_agent_interact

            url = str((args or {}).get("url") or "").strip()
            actions = (args or {}).get("actions")
            if not url:
                return {"success": False, "tool": tool_name, "error": "Missing required 'url' argument"}
            if not isinstance(actions, list) or not actions:
                return {"success": False, "tool": tool_name, "error": "Missing required 'actions' array"}
            approval_id = str((args or {}).get("approval_id") or (args or {}).get("approvalId") or "") or None
            try:
                payload = await browser_agent_interact(
                    url,
                    actions=actions,
                    settings=ctx.settings,
                    approval_id=approval_id,
                )
            except BrowserAgentError as exc:
                return {"success": False, "tool": tool_name, "error": str(exc), "error_code": exc.code}
            except Exception as exc:  # noqa: BLE001
                logger.exception("browser_agent_interact_failed url=%s", url[:120])
                return {"success": False, "tool": tool_name, "error": str(exc)}
            if payload.get("pending_approval"):
                return {
                    "success": False,
                    "tool": tool_name,
                    "pending_approval": True,
                    "message": payload.get("message"),
                }
            return {"success": True, "tool": tool_name, "result": payload}

        if spec.always_available and tool_name == "web_search":
            from app.services.web_research import TavilyNotConfiguredError, search_web

            query = str((args or {}).get("query") or "").strip()
            if not query:
                return {
                    "success": False,
                    "tool": tool_name,
                    "error": "Missing required 'query' argument",
                }
            try:
                payload = await search_web(query, settings=ctx.settings, max_results=5)
            except TavilyNotConfiguredError:
                return {
                    "success": False,
                    "tool": tool_name,
                    "error": (
                        "Web search is not configured for this environment. Set TAVILY_API_KEY."
                    ),
                    "query": query,
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("web_search_failed tool=%s query=%s", tool_name, query[:120])
                return {
                    "success": False,
                    "tool": tool_name,
                    "error": f"Web search temporarily unavailable: {exc}",
                    "query": query,
                }
            if payload.get("error"):
                return {
                    "success": False,
                    "tool": tool_name,
                    "error": str(payload["error"]),
                    "query": query,
                }
            return {
                "success": True,
                "tool": tool_name,
                "query": query,
                "results": payload.get("results") or [],
                "sources": payload.get("sources") or [],
                "totalResults": payload.get("totalResults", 0),
            }

        if tool_name.startswith("assistant_"):
            return await self._execute_assistant_platform_tool(ctx, tool_name, args or {})

        raw_args = dict(args or {})
        try:
            mapped = spec.map_params(raw_args) if spec.map_params else raw_args
        except (TypeError, ValueError) as exc:
            return {"success": False, "tool": tool_name, "error": str(exc)}

        try:
            invoke_action = self.resolve_invoke_action(spec, mapped)
        except ValueError as exc:
            return {"success": False, "tool": tool_name, "error": str(exc)}

        invoke_params = {k: v for k, v in mapped.items() if not k.startswith("_")}

        if invoke_action not in self._registered:
            return {
                "success": False,
                "tool": tool_name,
                "error": f"Backend action not implemented: {invoke_action}",
            }

        try:
            timeout_s = int(ctx.connector_timeout_seconds or 30)
            result = await asyncio.wait_for(
                asyncio.to_thread(invoke_tool, ctx, invoke_action, invoke_params),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            from app.services.cache_service import get_cache_service

            cache = get_cache_service(ctx.settings)
            await cache.record_event("connector_timeout")
            return {
                "success": False,
                "tool": tool_name,
                "action": invoke_action,
                "error": (
                    f"{spec.integration} did not respond within {timeout_s}s. "
                    "Partial results may omit this connected system."
                ),
                "error_code": "connector_timeout",
                "partial": True,
            }
        except ToolNotFoundError as exc:
            return {"success": False, "tool": tool_name, "error": str(exc)}
        except ToolError as exc:
            return {
                "success": False,
                "tool": tool_name,
                "action": invoke_action,
                "error": str(exc),
                "error_code": exc.code,
            }
        except Exception as exc:
            logger.exception(
                "tool_registry_execute_failed tool=%s action=%s",
                tool_name,
                invoke_action,
            )
            return {"success": False, "tool": tool_name, "error": str(exc)}

        if result.success:
            return {
                "success": True,
                "tool": tool_name,
                "action": invoke_action,
                "result": result.data,
                "connector_id": result.connector_id,
            }
        return {
            "success": False,
            "tool": tool_name,
            "action": invoke_action,
            "error": result.error_message or "Tool invocation failed",
            "error_code": result.error_code,
        }

    async def _execute_assistant_platform_tool(
        self,
        ctx: ToolContext,
        tool_name: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        from app.services import assistant_tools as assistant_tools_module

        org_id = ctx.org_id
        settings = ctx.settings
        agent_id = str(args.get("agentId") or args.get("agent_id") or ctx.agent_id or "") or None
        user_id = ctx.actor_id if ctx.actor_id not in {None, "", "system"} else None
        try:
            if tool_name == "assistant_agent_status":
                payload = assistant_tools_module.tool_agent_status(
                    org_id, settings, agent_id=agent_id
                )
            elif tool_name == "assistant_connector_status":
                payload = assistant_tools_module.tool_connector_status(
                    org_id, settings, environment_name=ctx.environment_name
                )
            elif tool_name == "assistant_workflow_runs":
                payload = assistant_tools_module.tool_workflow_runs(
                    org_id,
                    settings,
                    limit=int(args.get("limit") or 10),
                    status_filter=str(args.get("status")).strip() if args.get("status") else None,
                )
            elif tool_name == "assistant_analytics":
                payload = assistant_tools_module.tool_analytics(
                    org_id, settings, user_id=user_id
                )
            elif tool_name == "assistant_generate_document":
                topic = str(args.get("topic") or args.get("query") or "").strip()
                payload = await assistant_tools_module.tool_generate_document(org_id, topic, settings)
            elif tool_name == "assistant_run_agent_task":
                task = str(args.get("task") or args.get("query") or "").strip()
                payload = await assistant_tools_module.tool_run_agent_task(
                    org_id,
                    task,
                    settings,
                    agent_id=agent_id,
                    user_id=user_id,
                )
            elif tool_name == "assistant_create_workflow":
                goal = str(args.get("goal") or args.get("query") or args.get("name") or "").strip()
                payload = assistant_tools_module.tool_create_workflow(
                    org_id,
                    goal,
                    settings,
                    user_id=user_id,
                )
            elif tool_name == "assistant_execute_workflow":
                goal = str(args.get("query") or args.get("goal") or args.get("name") or "").strip()
                payload = assistant_tools_module.tool_execute_workflow(
                    org_id,
                    goal,
                    settings,
                    user_id=user_id,
                    environment_name=ctx.environment_name,
                )
            elif tool_name == "assistant_dependency_impact":
                payload = await assistant_tools_module.tool_dependency_impact(
                    org_id,
                    settings,
                    question=str(args.get("question") or args.get("query") or "").strip(),
                    entity_type=str(args.get("entity_type") or args.get("entityType") or "").strip() or None,
                    entity_id=str(args.get("entity_id") or args.get("entityId") or "").strip() or None,
                )
            else:
                return {"success": False, "tool": tool_name, "error": f"Unknown assistant tool: {tool_name}"}
            if payload.get("error"):
                return {"success": False, "tool": tool_name, "result": payload, "error": payload.get("error")}
            return {"success": True, "tool": tool_name, "result": payload}
        except Exception as exc:  # noqa: BLE001
            logger.warning("assistant_platform_tool_failed tool=%s error=%s", tool_name, exc)
            return {"success": False, "tool": tool_name, "error": str(exc)}


_tool_registry_singleton: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _tool_registry_singleton
    if _tool_registry_singleton is None:
        _tool_registry_singleton = ToolRegistry()
    return _tool_registry_singleton


def tool_registry() -> ToolRegistry:
    """Alias for get_tool_registry()."""
    return get_tool_registry()
