"""Department role pack catalog for agent marketplace (STA-121)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RequiredConnector:
    connector_type: str
    label: str
    required: bool = True
    connect_path: str = "/connectors"


@dataclass(frozen=True)
class DepartmentPackSpec:
    pack_id: str
    name: str
    department: str
    description: str
    agents: list[dict[str, Any]]
    rag_sources: list[dict[str, Any]]
    workflow_name: str
    workflow_description: str
    workflow_steps: list[dict[str, Any]]
    required_connectors: list[RequiredConnector] = field(default_factory=list)
    marketplace_tags: list[str] = field(default_factory=list)


def _org_namespace(org_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(org_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"gravitre-org:{org_id}")


def pack_seed_id(org_id: str, label: str) -> str:
    return str(uuid.uuid5(_org_namespace(org_id), f"department-pack:{label}"))


def list_pack_specs() -> list[DepartmentPackSpec]:
    return [
        DepartmentPackSpec(
            pack_id="sales-ops",
            name="Sales Operations Pack",
            department="Sales",
            description="Lead qualifier agent, CRM playbook RAG, and inbound lead workflow.",
            marketplace_tags=["sales", "hubspot", "crm"],
            required_connectors=[
                RequiredConnector("hubspot", "HubSpot CRM", connect_path="/connectors?type=hubspot"),
            ],
            agents=[
                {
                    "seed_label": "agent:lead-qualifier",
                    "name": "Lead Qualifier Agent",
                    "purpose": "Scores inbound leads, updates CRM fields, and routes high-intent opportunities.",
                    "role": "Sales Development",
                    "department": "Sales",
                    "model": "gpt-4.1",
                    "capabilities": ["lead-qualification", "crm-sync"],
                    "systems": ["hubspot"],
                    "config": {"departmentPack": "sales-ops", "type": "lead_qualifier"},
                },
                {
                    "seed_label": "agent:deal-desk",
                    "name": "Deal Desk Agent",
                    "purpose": "Reviews qualified opportunities and prepares handoff notes for account executives.",
                    "role": "Sales Operations",
                    "department": "Sales",
                    "model": "claude-sonnet-4-6",
                    "capabilities": ["deal-review", "crm-read"],
                    "systems": ["hubspot"],
                    "config": {"departmentPack": "sales-ops", "type": "deal_desk"},
                },
            ],
            rag_sources=[
                {
                    "seed_label": "rag:sales-playbook",
                    "title": "Sales Playbook",
                    "type": "manual",
                    "metadata": {
                        "description": "Upload your ICP criteria, objection handling, and qualification rubric.",
                        "departmentPack": "sales-ops",
                    },
                }
            ],
            workflow_name="Inbound lead → qualify → deal desk",
            workflow_description="HubSpot contact lookup, lead scoring, and deal desk handoff.",
            workflow_steps=[
                {
                    "id": "hubspot_lookup",
                    "name": "HubSpot contact lookup",
                    "type": "invoke_tool",
                    "config": {
                        "action": "hubspot.search_contacts",
                        "param_sources": {"query": "$email", "limit": 5},
                    },
                    "requires_connector": "hubspot",
                },
                {
                    "id": "qualify",
                    "name": "Lead qualification",
                    "type": "agent",
                    "metadata": {
                        "agent_seed": "agent:lead-qualifier",
                        "task": (
                            "Assignment: score this lead and summarize fit against the sales "
                            "playbook. Cite HubSpot lookup signals; do not invent firmographics. "
                            "Notify with score and recommended next step."
                        ),
                    },
                },
                {
                    "id": "deal_desk",
                    "name": "Deal desk review",
                    "type": "agent",
                    "metadata": {
                        "agent_seed": "agent:deal-desk",
                        "task": (
                            "Assignment: review qualification output and recommend the next sales "
                            "action (demo, nurture, or disqualify). Notify deal-desk decision."
                        ),
                    },
                },
            ],
        ),
        DepartmentPackSpec(
            pack_id="marketing-ops",
            name="Marketing Operations Pack",
            department="Marketing",
            description="Campaign agent, brand RAG source, and nurture enrollment workflow.",
            marketplace_tags=["marketing", "hubspot", "slack"],
            required_connectors=[
                RequiredConnector("hubspot", "HubSpot Marketing Hub", connect_path="/connectors?type=hubspot"),
                RequiredConnector("slack", "Slack notifications", required=False, connect_path="/connectors?type=slack"),
            ],
            agents=[
                {
                    "seed_label": "agent:campaign-coordinator",
                    "name": "Campaign Coordinator Agent",
                    "purpose": "Drafts nurture copy and enrolls qualified contacts into sequences.",
                    "role": "Marketing Operations",
                    "department": "Marketing",
                    "model": "claude-sonnet-4-6",
                    "capabilities": ["sequence-enrollment", "copy-drafting"],
                    "systems": ["hubspot", "slack"],
                    "config": {"departmentPack": "marketing-ops", "type": "campaign_coordinator"},
                }
            ],
            rag_sources=[
                {
                    "seed_label": "rag:brand-voice",
                    "title": "Brand Voice & Campaign Library",
                    "type": "manual",
                    "metadata": {
                        "description": "Upload brand guidelines, nurture templates, and campaign briefs.",
                        "departmentPack": "marketing-ops",
                    },
                }
            ],
            workflow_name="Qualified lead → nurture enrollment",
            workflow_description="Enroll contacts into nurture and notify marketing in Slack.",
            workflow_steps=[
                {
                    "id": "enroll",
                    "name": "Enroll in sequence",
                    "type": "invoke_tool",
                    "config": {
                        "action": "hubspot.enroll_contact_in_sequence",
                        "param_sources": {"contact_id": "$contact_id", "sequence_id": "$sequence_id"},
                    },
                    "requires_connector": "hubspot",
                },
                {
                    "id": "notify",
                    "name": "Slack campaign alert",
                    "type": "slack_post_message",
                    "config": {
                        "channel": "$slack_channel",
                        "message_input_key": "message",
                    },
                    "requires_connector": "slack",
                },
                {
                    "id": "review",
                    "name": "Campaign review",
                    "type": "agent",
                    "metadata": {
                        "agent_seed": "agent:campaign-coordinator",
                        "task": (
                            "Assignment: summarize sequence enrollment outcome and suggest follow-up "
                            "campaign actions. Flag Slack/HubSpot gaps. Notify marketing ops."
                        ),
                    },
                },
            ],
        ),
        DepartmentPackSpec(
            pack_id="support-ops",
            name="Customer Support Pack",
            department="Support",
            description="Ticket triage agent, help-center RAG, and escalation workflow.",
            marketplace_tags=["support", "zendesk"],
            required_connectors=[
                RequiredConnector("zendesk", "Zendesk Support", connect_path="/connectors?type=zendesk"),
            ],
            agents=[
                {
                    "seed_label": "agent:ticket-triage",
                    "name": "Ticket Triage Agent",
                    "purpose": "Classifies support tickets, suggests macros, and escalates priority cases.",
                    "role": "Support Operations",
                    "department": "Support",
                    "model": "gpt-4.1",
                    "capabilities": ["ticket-triage", "macro-suggestion"],
                    "systems": ["zendesk"],
                    "config": {"departmentPack": "support-ops", "type": "ticket_triage"},
                }
            ],
            rag_sources=[
                {
                    "seed_label": "rag:help-center",
                    "title": "Help Center Knowledge",
                    "type": "manual",
                    "metadata": {
                        "description": "Sync or upload help articles for retrieval during ticket triage.",
                        "departmentPack": "support-ops",
                    },
                }
            ],
            workflow_name="New ticket → triage → escalation",
            workflow_description="Zendesk ticket lookup and AI triage with escalation path.",
            workflow_steps=[
                {
                    "id": "ticket_lookup",
                    "name": "Fetch ticket context",
                    "type": "invoke_tool",
                    "config": {
                        "action": "zendesk.tickets.get",
                        "param_sources": {"ticket_id": "$ticket_id"},
                    },
                    "requires_connector": "zendesk",
                },
                {
                    "id": "triage",
                    "name": "AI ticket triage",
                    "type": "agent",
                    "metadata": {
                        "agent_seed": "agent:ticket-triage",
                        "task": (
                            "Assignment: classify urgency from Zendesk ticket context, suggest a "
                            "response macro from help-center knowledge, and flag escalation if "
                            "SLA risk is present. Notify with triage outcome."
                        ),
                    },
                },
            ],
        ),
        DepartmentPackSpec(
            pack_id="finance-ops",
            name="Finance Operations Pack",
            department="Finance",
            description="AR analyst agent, policy RAG, and invoice review workflow.",
            marketplace_tags=["finance", "quickbooks"],
            required_connectors=[
                RequiredConnector("quickbooks", "QuickBooks Online", connect_path="/connectors?type=quickbooks"),
            ],
            agents=[
                {
                    "seed_label": "agent:ar-analyst",
                    "name": "AR Analyst Agent",
                    "purpose": "Reviews open invoices, flags overdue accounts, and drafts collections notes.",
                    "role": "Accounts Receivable",
                    "department": "Finance",
                    "model": "gpt-4.1",
                    "capabilities": ["invoice-review", "collections"],
                    "systems": ["quickbooks"],
                    "config": {"departmentPack": "finance-ops", "type": "ar_analyst"},
                }
            ],
            rag_sources=[
                {
                    "seed_label": "rag:collections-policy",
                    "title": "Collections & AR Policy",
                    "type": "manual",
                    "metadata": {
                        "description": "Upload AR policy, dunning schedules, and approval thresholds.",
                        "departmentPack": "finance-ops",
                    },
                }
            ],
            workflow_name="Overdue invoice → AR review",
            workflow_description="QuickBooks invoice lookup and AR analyst review.",
            workflow_steps=[
                {
                    "id": "invoice_lookup",
                    "name": "Fetch invoice",
                    "type": "invoke_tool",
                    "config": {
                        "action": "quickbooks.get_invoice",
                        "param_sources": {"invoice_id": "$invoice_id"},
                    },
                    "requires_connector": "quickbooks",
                },
                {
                    "id": "ar_review",
                    "name": "AR analyst review",
                    "type": "agent",
                    "metadata": {
                        "agent_seed": "agent:ar-analyst",
                        "task": (
                            "Assignment: summarize QuickBooks invoice status against AR policy and "
                            "recommend the collections next step. Notify finance with overdue risk."
                        ),
                    },
                },
            ],
        ),
    ]


def get_pack_spec(pack_id: str) -> DepartmentPackSpec | None:
    for spec in list_pack_specs():
        if spec.pack_id == pack_id:
            return spec
    return None
