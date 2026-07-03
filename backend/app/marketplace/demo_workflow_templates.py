"""Demo workflow templates for agent knowledge assignment onboarding."""
from __future__ import annotations

from typing import Any

AGENT_KNOWLEDGE_DEMO_WORKFLOWS: tuple[dict[str, Any], ...] = (
    {
        "id": "demo-launch-campaign",
        "name": "Launch a Campaign",
        "description": "Review approved brand guidelines, draft launch checklist, and route for approval before publishing.",
        "department": "marketing",
        "riskLevel": "medium",
        "requiresApproval": True,
        "requiredConnectors": ["google_drive", "slack"],
        "optionalConnectors": ["hubspot", "canva"],
        "knowledgeAssignments": [
            {
                "sourceType": "google_drive_folder",
                "label": "Brand guidelines",
                "includeRules": ["brand", "guideline", "approved"],
            },
            {
                "sourceType": "knowledge_pack",
                "label": "Campaign playbook",
            },
        ],
        "steps": [
            {"id": "trigger", "name": "Campaign request", "type": "trigger"},
            {"id": "retrieve_brand", "name": "Retrieve brand guidelines", "type": "rag_retrieve"},
            {"id": "draft_plan", "name": "Draft launch plan", "type": "agent_task"},
            {"id": "approval", "name": "Manager approval", "type": "approval_gate"},
            {"id": "notify", "name": "Notify launch channel", "type": "invoke_tool", "action": "slack.post_message"},
        ],
        "sampleOutput": "Launch checklist with approved messaging, channel plan, and approval record.",
        "businessValue": "Reduces off-brand launches by grounding the agent in approved sources only.",
    },
    {
        "id": "demo-stale-deals",
        "name": "Find Stale Deals",
        "description": "Surface stale pipeline deals using CRM data and assigned sales playbook knowledge.",
        "department": "sales",
        "riskLevel": "low",
        "requiresApproval": False,
        "requiredConnectors": ["hubspot"],
        "optionalConnectors": ["slack"],
        "knowledgeAssignments": [
            {
                "sourceType": "hubspot_object",
                "label": "Open deals view",
            },
            {
                "sourceType": "knowledge_pack",
                "label": "Sales playbook",
            },
        ],
        "steps": [
            {"id": "trigger", "name": "Daily pipeline review", "type": "trigger"},
            {"id": "query_crm", "name": "Query stale deals", "type": "invoke_tool", "action": "hubspot.search_deals"},
            {"id": "enrich", "name": "Enrich with playbook guidance", "type": "rag_retrieve"},
            {"id": "summarize", "name": "Summarize follow-ups", "type": "agent_task"},
        ],
        "sampleOutput": "Ranked stale deals with recommended next actions from the assigned playbook.",
        "businessValue": "Keeps reps focused on high-value follow-ups without exporting raw CRM dumps.",
    },
    {
        "id": "demo-customer-risk",
        "name": "Summarize Customer Risk",
        "description": "Combine support history, account notes, and approved risk policy references.",
        "department": "customer_success",
        "riskLevel": "medium",
        "requiresApproval": True,
        "requiredConnectors": ["zendesk", "hubspot"],
        "optionalConnectors": ["slack"],
        "knowledgeAssignments": [
            {
                "sourceType": "zendesk_view",
                "label": "At-risk accounts view",
            },
            {
                "sourceType": "sharepoint_folder",
                "label": "Customer risk policy",
                "excludeRules": ["legal", "hr"],
            },
        ],
        "steps": [
            {"id": "trigger", "name": "Risk review request", "type": "trigger"},
            {"id": "load_tickets", "name": "Load recent tickets", "type": "invoke_tool", "action": "zendesk.search_tickets"},
            {"id": "policy", "name": "Apply risk policy", "type": "rag_retrieve"},
            {"id": "brief", "name": "Generate risk brief", "type": "agent_task"},
            {"id": "approval", "name": "CS lead approval", "type": "approval_gate"},
        ],
        "sampleOutput": "Customer risk brief with evidence links and recommended escalation path.",
        "businessValue": "Accelerates account reviews while preserving reference-only storage.",
    },
    {
        "id": "demo-support-triage",
        "name": "Support Triage Report",
        "description": "Triage open support tickets using assigned knowledge base and escalation rules.",
        "department": "support",
        "riskLevel": "low",
        "requiresApproval": False,
        "requiredConnectors": ["zendesk"],
        "optionalConnectors": ["slack", "confluence"],
        "knowledgeAssignments": [
            {
                "sourceType": "confluence_space",
                "label": "Support runbooks",
            },
            {
                "sourceType": "slack_channel",
                "label": "#support-escalations",
            },
        ],
        "steps": [
            {"id": "trigger", "name": "Hourly triage", "type": "trigger"},
            {"id": "queue", "name": "Load open tickets", "type": "invoke_tool", "action": "zendesk.list_tickets"},
            {"id": "runbooks", "name": "Match runbooks", "type": "rag_retrieve"},
            {"id": "report", "name": "Publish triage report", "type": "agent_task"},
        ],
        "sampleOutput": "Prioritized ticket queue with suggested runbook links and escalation hints.",
        "businessValue": "Speeds first response while keeping agents scoped to approved support knowledge.",
    },
)


def list_agent_knowledge_demo_workflows() -> list[dict[str, Any]]:
    return [dict(row) for row in AGENT_KNOWLEDGE_DEMO_WORKFLOWS]


def get_agent_knowledge_demo_workflow(workflow_id: str) -> dict[str, Any] | None:
    for row in AGENT_KNOWLEDGE_DEMO_WORKFLOWS:
        if row["id"] == workflow_id:
            return dict(row)
    return None
